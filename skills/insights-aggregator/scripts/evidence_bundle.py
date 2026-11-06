"""Import prepared evidence without reading raw sessions or manufacturing facets."""

import copy
import json


def load_bundle(path, empty_group, parse_iso):
    with open(path, encoding="utf-8") as fh:
        bundle = json.load(fh)
    if bundle.get("schema_version") != 1:
        raise ValueError("evidence bundle schema_version must be 1")
    if not parse_iso(bundle.get("generated_at")):
        raise ValueError("evidence bundle requires generated_at (ISO 8601)")
    selection = bundle.get("selection")
    if not isinstance(selection, dict) or not selection.get("method") or "limits" not in selection:
        raise ValueError("selection requires method and limits")
    metrics = bundle.get("metrics") or {}
    if not metrics.get("by_agent"):
        raise ValueError("metrics.by_agent must identify at least one observed tool")

    def group(values):
        if not isinstance(values, dict) or values.keys() - empty_group.keys():
            raise ValueError("metric group has unknown keys or is not an object")
        result = copy.deepcopy(empty_group)
        for key, default in empty_group.items():
            value = values.get(key)
            if value is None:
                result[key] = copy.deepcopy(default) if isinstance(default, (dict, list)) else None
            elif isinstance(default, dict):
                if not isinstance(value, dict):
                    raise ValueError(f"{key} must be an object")
                result[key] = value
            elif isinstance(default, list):
                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a list")
                result[key] = value
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"{key} must be a nonnegative number or null")
                result[key] = value
        result["available_metrics"] = sorted(k for k, v in values.items() if v is not None)
        return result

    sources = bundle.get("sources") or []
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    ids = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not source["id"] or not source.get("locator"):
            raise ValueError("each source requires id and locator")
        ids.append(source["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("source ids must be unique")
    cross = metrics.get("cross_tool")
    # Empty containers are display defaults, explicitly marked unavailable.
    cross_default = {"overlap": {}, "handoffs": {"direction_counts": {}, "examples": []},
                     "project_tool_matrix": {}}
    return {
        "generated_at": bundle["generated_at"],
        "window": bundle.get("window") or {},
        "display_timezone": bundle.get("display_timezone"),
        "input_mode": "evidence_bundle",
        "selection": selection,
        "sources": sources,
        "knowledge_candidates": bundle.get("knowledge_candidates") or [],
        "infrastructure_observations": bundle.get("infrastructure_observations") or [],
        "combined": group(metrics.get("combined") or {}),
        "by_agent": {agent: group(values) for agent, values in metrics["by_agent"].items()},
        "cross_tool": cross if cross is not None else cross_default,
        "cross_tool_metrics_available": cross is not None,
        "internal_sessions_excluded": bundle.get("internal_sessions_excluded"),
        "internal_model_effort": bundle.get("internal_model_effort") or {},
    }
