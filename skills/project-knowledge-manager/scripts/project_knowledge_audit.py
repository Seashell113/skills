#!/usr/bin/env python3
"""Heuristic project knowledge structure audit.

This script intentionally checks only deterministic or low-risk heuristics.
Semantic truthfulness still needs human/agent review against project reality.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


IGNORED_FILES = {".DS_Store"}
OPTIONAL_DIRS = ["docs", ".agents", "openspec"]
DOCS_SUBDIRS = ["context", "standards", "runbooks", "adr"]
TOOL_SPECIFIC_DIRS = [".cursor", ".windsurf", ".claude"]
HIGH_RISK_HINTS = re.compile(r"(auth|permission|role|pay|payment|approval|route|config|security|权限|支付|审批|路由|配置|安全)")
COMMAND_LINE = re.compile(r"^\s*(npm|pnpm|yarn|bun|npx|cargo|go|python|pytest|make)\b")


@dataclass
class Finding:
    severity: str
    path: str
    issue: str
    evidence: str
    recommendation: str


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def has_real_files(path: Path) -> bool:
    if not path.exists():
        return False
    for child in path.rglob("*"):
        if child.is_file() and child.name not in IGNORED_FILES:
            return True
    return False


def is_empty_dir(path: Path) -> bool:
    return path.exists() and path.is_dir() and not has_real_files(path)


def nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def command_lines(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if COMMAND_LINE.search(line)}


def markdown_files(root: Path, base: str) -> Iterable[Path]:
    start = root / base
    if not start.exists():
        return []
    return start.rglob("*.md")


def audit(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    readme = root / "README.md"
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"

    if not readme.exists():
        findings.append(Finding(
            "P1",
            "README.md",
            "Missing human project entry.",
            "No root README.md found.",
            "Create a short README with project purpose, setup, commands, and key links.",
        ))

    if not agents.exists():
        findings.append(Finding(
            "P1",
            "AGENTS.md",
            "Missing agent project entry.",
            "No root AGENTS.md found.",
            "Create a concise AGENTS.md with project-specific constraints, risks, and verification expectations.",
        ))

    if not claude.exists():
        findings.append(Finding(
            "P2",
            "CLAUDE.md",
            "Missing Claude Code adapter.",
            "No root CLAUDE.md found.",
            "Create a thin CLAUDE.md containing @AGENTS.md when Claude Code compatibility is required.",
        ))
    else:
        claude_lines = nonempty_lines(read_text(claude))
        first = claude_lines[0] if claude_lines else ""
        if "@AGENTS.md" not in first:
            findings.append(Finding(
                "P1",
                "CLAUDE.md",
                "CLAUDE.md does not thinly reference AGENTS.md first.",
                f"First non-empty line is: {first!r}.",
                "Make CLAUDE.md a thin adapter that starts with @AGENTS.md.",
            ))
        if len(claude_lines) > 12:
            findings.append(Finding(
                "P2",
                "CLAUDE.md",
                "CLAUDE.md may be maintaining a second rule set.",
                f"Found {len(claude_lines)} non-empty lines.",
                "Move project rules to AGENTS.md and keep only Claude Code-specific additions here.",
            ))

    for name in OPTIONAL_DIRS:
        path = root / name
        if is_empty_dir(path):
            findings.append(Finding(
                "P2",
                name,
                "Optional knowledge directory exists without real content.",
                f"{name}/ exists but contains no non-ignored files.",
                "Remove it until there is real information density, or add an entry document explaining its purpose.",
            ))

    docs = root / "docs"
    if docs.exists():
        if not (docs / "README.md").exists() and has_real_files(docs):
            findings.append(Finding(
                "P2",
                "docs/README.md",
                "docs exists without navigation.",
                "docs/ contains files but no docs/README.md.",
                "Add docs/README.md that maps context, standards, runbooks, ADRs, and points behavior specs to openspec/.",
            ))
        for subdir in DOCS_SUBDIRS:
            path = docs / subdir
            if is_empty_dir(path):
                findings.append(Finding(
                    "P3",
                    f"docs/{subdir}/",
                    "Empty docs subdirectory.",
                    f"docs/{subdir}/ has no real files.",
                    "Avoid placeholder directories unless the team has agreed to keep the structure visible.",
                ))

    readme_text = read_text(readme) if readme.exists() else ""
    agents_text = read_text(agents) if agents.exists() else ""

    if agents.exists():
        agent_lines = nonempty_lines(agents_text)
        if len(agent_lines) > 220:
            findings.append(Finding(
                "P2",
                "AGENTS.md",
                "AGENTS.md looks too long for an agent entry file.",
                f"Found {len(agent_lines)} non-empty lines.",
                "Move long background, tutorials, and standards into README, docs/, openspec/, or .agents/ as appropriate.",
            ))

        duplicated_commands = sorted(command_lines(readme_text) & command_lines(agents_text))
        if len(duplicated_commands) >= 2:
            evidence = "; ".join(duplicated_commands[:5])
            findings.append(Finding(
                "P2",
                "AGENTS.md",
                "AGENTS.md appears to duplicate README command details.",
                evidence,
                "Keep command truth in README.md and mention only agent-specific verification strategy in AGENTS.md.",
            ))

        if re.search(r"(团队通用|全团队|统一 Git|commit 信息|提交信息)", agents_text):
            findings.append(Finding(
                "P2",
                "AGENTS.md",
                "AGENTS.md may contain team-wide rules.",
                "Found terms associated with team-wide process or Git rules.",
                "Move team-wide rules to the team public layer unless this project has a specific exception.",
            ))

    if (root / "openspec").exists() and docs.exists():
        spec_terms = []
        for path in markdown_files(root, "docs"):
            text = read_text(path)
            if re.search(r"(验收标准|需求规格|系统行为|业务规则 delta|acceptance criteria|requirement)", text, re.I):
                spec_terms.append(str(path.relative_to(root)))
        if spec_terms:
            findings.append(Finding(
                "P2",
                "docs/",
                "docs may duplicate behavior/specification content while openspec exists.",
                ", ".join(spec_terms[:6]),
                "Keep behavior specs and acceptance criteria in openspec/; keep docs/ for supporting knowledge.",
            ))

    for tool_dir in TOOL_SPECIFIC_DIRS:
        path = root / tool_dir
        if path.exists() and has_real_files(path) and not (root / ".agents").exists():
            findings.append(Finding(
                "P2",
                tool_dir,
                "Tool-specific directory exists without a neutral .agents source.",
                f"{tool_dir}/ contains files.",
                "Confirm whether this is only an adapter. Prefer AGENTS.md or .agents/ as the neutral source of truth.",
            ))

    module_agents = [
        path for path in root.rglob("AGENTS.md")
        if path != agents and "node_modules" not in path.parts and ".git" not in path.parts
    ]
    if len(module_agents) > 5:
        findings.append(Finding(
            "P2",
            "*/AGENTS.md",
            "Many local AGENTS.md files found.",
            f"Found {len(module_agents)} non-root AGENTS.md files.",
            "Keep local AGENTS.md only for high-risk modules; use module README for normal module knowledge.",
        ))
    for path in module_agents:
        rel = path.relative_to(root)
        if not HIGH_RISK_HINTS.search(str(rel)):
            findings.append(Finding(
                "P3",
                str(rel),
                "Local AGENTS.md may need justification.",
                "Path does not contain obvious high-risk module hints.",
                "Confirm the module is high risk; otherwise move durable knowledge to module README.md.",
            ))

    module_readmes = [
        path for path in root.rglob("README.md")
        if path != readme and "node_modules" not in path.parts and ".git" not in path.parts
    ]
    for path in module_readmes:
        text = read_text(path)
        if re.search(r"```.*\b(interface|type|class)\b|字段列表|参数列表|类型定义", text, re.S):
            findings.append(Finding(
                "P3",
                str(path.relative_to(root)),
                "Module README may be copying code-level details.",
                "Found type/signature/list wording.",
                "Keep type signatures and field details in code; use README for responsibility, flow, rationale, pitfalls, and verification.",
            ))

    return findings


def render_markdown(root: Path, findings: list[Finding]) -> str:
    if not findings:
        return (
            "# Project Knowledge Audit\n\n"
            f"Project root: `{root}`\n\n"
            "No structural findings from deterministic checks. Still review semantic accuracy and source-of-truth ownership manually.\n"
        )

    lines = [
        "# Project Knowledge Audit",
        "",
        f"Project root: `{root}`",
        "",
        "## Findings",
        "",
        "| Severity | Path | Issue | Evidence | Recommended action |",
        "|---|---|---|---|---|",
    ]
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for finding in sorted(findings, key=lambda item: (order.get(item.severity, 9), item.path)):
        lines.append(
            "| {severity} | `{path}` | {issue} | {evidence} | {recommendation} |".format(
                severity=finding.severity,
                path=finding.path.replace("|", "\\|"),
                issue=finding.issue.replace("|", "\\|"),
                evidence=finding.evidence.replace("|", "\\|"),
                recommendation=finding.recommendation.replace("|", "\\|"),
            )
        )
    lines.extend([
        "",
        "## Manual Review Still Needed",
        "",
        "- Check whether documented claims are still true against code, scripts, CI, and recent incidents.",
        "- Check whether behavior specs live in `openspec/` when OpenSpec is used.",
        "- Check whether team-wide rules are referenced from public sources instead of copied locally.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit project knowledge directory structure.")
    parser.add_argument("project", nargs="?", default=".", help="Project root to audit.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown.")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project root does not exist or is not a directory: {root}")

    findings = audit(root)
    if args.json:
        print(json.dumps({
            "project_root": str(root),
            "findings": [asdict(item) for item in findings],
        }, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(root, findings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

