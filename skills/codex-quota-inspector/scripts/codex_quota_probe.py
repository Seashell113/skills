#!/usr/bin/env python3
"""Read local Codex quota and ChatGPT reset credits without printing secrets."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"
SECRET_VALUE_MARKERS = ("eyJ", "Bearer ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["quota", "credits", "all", "diagnose"], help="Query mode")
    parser.add_argument("--timezone", default=None, help="IANA timezone, e.g. Asia/Shanghai")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--codex-home", default=os.path.expanduser("~/.codex"))
    parser.add_argument("--source", choices=["auto", "live", "local"], default="auto", help="Quota source. Default: live API with local fallback")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent rate limit events for diagnose mode")
    return parser.parse_args()


def get_tz(name: str | None) -> dt.tzinfo | None:
    if name and ZoneInfo:
        return ZoneInfo(name)
    if ZoneInfo:
        local_name = dt.datetime.now().astimezone().tzinfo
        return local_name
    return None


def format_time(value: Any, timezone: dt.tzinfo | None) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            timestamp = value / 1000 if value > 10_000_000_000 else value
            converted = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
        elif isinstance(value, str):
            converted = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if converted.tzinfo is None:
                converted = converted.replace(tzinfo=dt.timezone.utc)
        else:
            return str(value)
        if timezone:
            converted = converted.astimezone(timezone)
        return converted.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return str(value)


def quota_snapshot(codex_home: str, timezone: dt.tzinfo | None, source: str) -> dict[str, Any]:
    if source == "live":
        return live_rate_limits(codex_home, timezone)
    if source == "local":
        return latest_local_rate_limits(codex_home, timezone)

    live = live_rate_limits(codex_home, timezone)
    if live.get("ok"):
        return live

    local = latest_local_rate_limits(codex_home, timezone)
    local["fallback_reason"] = live.get("error")
    local["fallback_from"] = "live_api"
    return local


def live_rate_limits(codex_home: str, timezone: dt.tzinfo | None) -> dict[str, Any]:
    credentials = load_auth_credentials(codex_home)
    if not credentials.get("ok"):
        return {
            "ok": False,
            "source_type": "live_api",
            "source": USAGE_URL,
            "error": credentials.get("error"),
            "shape": credentials.get("shape"),
        }

    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {credentials['access_token']}",
            "OpenAI-Account": str(credentials["account_id"]),
            "User-Agent": "codex-quota-inspector",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "source_type": "live_api", "source": USAGE_URL, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "source_type": "live_api", "source": USAGE_URL, "error": f"{type(exc).__name__}: {exc}"}

    if not isinstance(body, dict):
        return {"ok": False, "source_type": "live_api", "source": USAGE_URL, "error": "接口返回不是对象"}

    parsed = parse_live_usage_payload(body, timezone)
    parsed.update(
        {
            "source_type": "live_api",
            "source": USAGE_URL,
            "event_timestamp": format_time(dt.datetime.now(dt.timezone.utc).isoformat(), timezone),
        }
    )
    return parsed


def parse_live_usage_payload(body: dict[str, Any], timezone: dt.tzinfo | None) -> dict[str, Any]:
    rate_limit = body.get("rate_limit")
    if not isinstance(rate_limit, dict):
        return {
            "ok": False,
            "error": "live usage 响应缺少 rate_limit 对象",
            "plan_type": body.get("plan_type"),
        }

    windows = [
        live_window_to_snapshot(rate_limit.get("primary_window")),
        live_window_to_snapshot(rate_limit.get("secondary_window")),
    ]
    primary = find_window(windows, 300) or windows[0]
    secondary = find_window(windows, 10080) or windows[1]
    result = {
        "ok": True,
        "plan_type": body.get("plan_type"),
        "five_hour": parse_window(primary, timezone),
        "seven_day": parse_window(secondary, timezone),
    }
    return validate_quota_result(result)


def live_window_to_snapshot(window: Any) -> dict[str, Any]:
    if not isinstance(window, dict):
        return {}
    reset_at = pick(window, "reset_at", "resets_at", "resetAt", "resetsAt")
    window_seconds = pick(window, "limit_window_seconds", "window_seconds", "windowSeconds")
    window_minutes = pick(window, "window_minutes", "windowDurationMins", "window_duration_mins")
    if window_minutes is None and isinstance(window_seconds, (int, float)) and window_seconds > 0:
        window_minutes = int((window_seconds + 59) // 60)
    return {
        "used_percent": pick(window, "used_percent", "usedPercent"),
        "remaining_percent": pick(window, "remaining_percent", "remainingPercent"),
        "resets_at": reset_at,
        "window_minutes": window_minutes,
    }


def latest_local_rate_limits(codex_home: str, timezone: dt.tzinfo | None) -> dict[str, Any]:
    latest: tuple[str, str, dict[str, Any]] | None = None

    for timestamp, path, payload in iter_rate_limit_events(codex_home):
        if latest is None or timestamp > latest[0]:
            latest = (timestamp, path, payload)

    if latest is None:
        sessions_dir = os.path.join(codex_home, "sessions")
        return {"ok": False, "source_type": "local_snapshot", "error": "未找到 payload.rate_limits 事件", "source": sessions_dir}

    timestamp, source, payload = latest
    return parse_rate_limits_payload(timestamp, source, payload, timezone)


def iter_rate_limit_events(codex_home: str) -> list[tuple[str, str, dict[str, Any]]]:
    sessions_dir = os.path.join(codex_home, "sessions")
    paths = glob.glob(os.path.join(sessions_dir, "**", "*.jsonl"), recursive=True)
    events: list[tuple[str, str, dict[str, Any]]] = []

    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = event.get("payload")
                    if not isinstance(payload, dict) or "rate_limits" not in payload:
                        continue
                    timestamp = str(event.get("timestamp", ""))
                    events.append((timestamp, path, payload))
        except OSError:
            continue
    return events


def parse_rate_limits_payload(timestamp: str, source: str, payload: dict[str, Any], timezone: dt.tzinfo | None) -> dict[str, Any]:
    rate_limits = payload.get("rate_limits")
    if not isinstance(rate_limits, dict):
        return {
            "ok": False,
            "error": "payload.rate_limits 不是对象",
            "event_timestamp": format_time(timestamp, timezone),
            "source": source,
        }

    windows = [value for value in rate_limits.values() if isinstance(value, dict)]
    primary = find_window(windows, 300) or (rate_limits.get("primary") if isinstance(rate_limits.get("primary"), dict) else {})
    secondary = find_window(windows, 10080) or (rate_limits.get("secondary") if isinstance(rate_limits.get("secondary"), dict) else {})

    result = validate_quota_result({
        "source_type": "local_snapshot",
        "event_timestamp": format_time(timestamp, timezone),
        "source": source,
        "plan_type": rate_limits.get("plan_type") or payload.get("plan_type"),
        "five_hour": parse_window(primary, timezone),
        "seven_day": parse_window(secondary, timezone),
    })
    return result


def diagnose_rate_limits(codex_home: str, timezone: dt.tzinfo | None, limit: int) -> dict[str, Any]:
    events = sorted(iter_rate_limit_events(codex_home), key=lambda item: item[0], reverse=True)[: max(1, limit)]
    if not events:
        return {"ok": False, "error": "未找到 payload.rate_limits 事件", "source": os.path.join(codex_home, "sessions")}
    return {
        "ok": True,
        "note": "仅包含 rate_limits 的非敏感字段；不读取 auth.json，不输出 token/account_id。",
        "events": [diagnose_event(timestamp, source, payload, timezone) for timestamp, source, payload in events],
    }


def diagnose_event(timestamp: str, source: str, payload: dict[str, Any], timezone: dt.tzinfo | None) -> dict[str, Any]:
    rate_limits = payload.get("rate_limits")
    if not isinstance(rate_limits, dict):
        return {
            "event_timestamp": format_time(timestamp, timezone),
            "source": source,
            "error": "payload.rate_limits 不是对象",
        }
    parsed = parse_rate_limits_payload(timestamp, source, payload, timezone)
    windows = []
    for name, value in rate_limits.items():
        if not isinstance(value, dict):
            continue
        windows.append(
            {
                "name": name,
                "window_minutes": value.get("window_minutes"),
                "raw_used_percent": value.get("used_percent"),
                "raw_remaining_percent": value.get("remaining_percent"),
                "raw_resets_at": value.get("resets_at") or value.get("reset_at") or value.get("resetAt") or value.get("reset_time"),
                "parsed": parse_window(value, timezone),
            }
        )
    return {
        "event_timestamp": format_time(timestamp, timezone),
        "source": source,
        "plan_type": rate_limits.get("plan_type") or payload.get("plan_type"),
        "parsed_five_hour": parsed.get("five_hour"),
        "parsed_seven_day": parsed.get("seven_day"),
        "windows": windows,
    }


def parse_window(window: dict[str, Any], timezone: dt.tzinfo | None) -> dict[str, Any]:
    used_key, used = pick_item(window, "used", "used_count", "current", "used_percent")
    remaining_key, remaining = pick_item(window, "remaining", "remaining_count", "remaining_percent")
    reset_raw = pick(window, "resets_at", "reset_at", "resetAt", "reset_time")
    used_is_percent = used_key == "used_percent"
    remaining_is_percent = remaining_key == "remaining_percent"
    errors = []

    if used is None:
        errors.append("缺少真实 used_percent/used 字段")
    if reset_raw is None:
        errors.append("缺少真实 resets_at/reset_at 字段")

    if remaining is None and used_is_percent and isinstance(used, (int, float)):
        remaining = max(0, 100 - used)
        remaining_is_percent = True
    return {
        "ok": not errors,
        "errors": errors,
        "used": format_percent_if_needed(used, used_is_percent),
        "remaining": format_percent_if_needed(remaining, remaining_is_percent),
        "reset_at": format_time(reset_raw, timezone),
        "window_minutes": window.get("window_minutes"),
        "raw_used_percent": window.get("used_percent"),
        "raw_remaining_percent": window.get("remaining_percent"),
        "raw_reset_at": reset_raw,
    }


def validate_quota_result(result: dict[str, Any]) -> dict[str, Any]:
    errors = []
    for label, key in (("5 小时额度", "five_hour"), ("7 天额度", "seven_day")):
        window = result.get(key)
        if not isinstance(window, dict) or not window.get("ok"):
            detail = "；".join(window.get("errors", [])) if isinstance(window, dict) else "窗口对象缺失"
            errors.append(f"{label}无法确认：{detail}")
    result["ok"] = not errors
    result["errors"] = errors
    return result


def find_window(windows: list[dict[str, Any]], window_minutes: int) -> dict[str, Any] | None:
    for window in windows:
        if window.get("window_minutes") == window_minutes:
            return window
    return None


def pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def pick_item(data: dict[str, Any], *keys: str) -> tuple[str | None, Any]:
    for key in keys:
        if key in data:
            return key, data[key]
    return None, None


def format_percent_if_needed(value: Any, is_percent: bool) -> Any:
    if value is None:
        return None
    if is_percent and isinstance(value, (int, float)):
        return f"{value:g}%"
    return value


def display(value: Any) -> str:
    return "null" if value is None else str(value)


def display_window(window: dict[str, Any]) -> str:
    if not window.get("ok"):
        detail = "；".join(window.get("errors", [])) or "字段不完整"
        return f"无法确认（{detail}）"
    return f"已用 `{display(window.get('used'))}`，剩余 `{display(window.get('remaining'))}`，重置时间 `{display(window.get('reset_at'))}`"


def load_auth_shape(auth_path: str) -> dict[str, Any]:
    try:
        with open(auth_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        return {"ok": False, "error": f"无法读取 auth.json: {type(exc).__name__}"}
    tokens = data.get("tokens")
    return {
        "ok": True,
        "top_keys": sorted(data.keys()),
        "tokens_keys": sorted(tokens.keys()) if isinstance(tokens, dict) else None,
    }


def load_auth_credentials(codex_home: str) -> dict[str, Any]:
    auth_path = os.path.join(codex_home, "auth.json")
    try:
        with open(auth_path, "r", encoding="utf-8") as handle:
            auth = json.load(handle)
    except Exception as exc:
        return {"ok": False, "error": f"无法读取 auth.json: {type(exc).__name__}"}

    tokens = auth.get("tokens")
    if not isinstance(tokens, dict):
        return {"ok": False, "error": "auth.json 结构不符合预期", "shape": load_auth_shape(auth_path)}

    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not access_token or not account_id:
        return {"ok": False, "error": "缺少必要认证字段", "shape": load_auth_shape(auth_path)}

    return {"ok": True, "access_token": access_token, "account_id": account_id}


def reset_credits(codex_home: str, timezone: dt.tzinfo | None) -> dict[str, Any]:
    credentials = load_auth_credentials(codex_home)
    if not credentials.get("ok"):
        return {"ok": False, "error": credentials.get("error"), "shape": credentials.get("shape")}

    request = urllib.request.Request(
        RESET_CREDITS_URL,
        headers={
            "Authorization": f"Bearer {credentials['access_token']}",
            "OpenAI-Account": str(credentials["account_id"]),
            "User-Agent": "codex-quota-inspector",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}", "endpoint": RESET_CREDITS_URL}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "endpoint": RESET_CREDITS_URL}

    if not isinstance(body, dict):
        return {"ok": False, "error": "接口返回不是对象", "endpoint": RESET_CREDITS_URL}

    credits = body.get("credits")
    if credits is None:
        credits = body.get("items") or body.get("data") or []

    safe_credits = []
    if isinstance(credits, list):
        for credit in credits:
            if not isinstance(credit, dict):
                continue
            safe_credits.append(
                {
                    "status": credit.get("status"),
                    "granted_at": format_time(credit.get("granted_at"), timezone),
                    "expires_at": format_time(credit.get("expires_at"), timezone),
                    "used_at": format_time(credit.get("used_at"), timezone),
                }
            )

    available_count = body.get("available_count")
    if available_count is None:
        available_count = sum(1 for credit in safe_credits if credit.get("status") in {"available", "active", "unused"})

    return {
        "ok": True,
        "endpoint": RESET_CREDITS_URL,
        "available_count": available_count,
        "credits": safe_credits,
    }


def assert_no_sensitive_values(result: Any) -> None:
    serialized = json.dumps(result, ensure_ascii=False)
    for marker in SECRET_VALUE_MARKERS:
        if marker in serialized:
            raise RuntimeError("internal safety check failed: possible credential value in output")


def print_json(result: dict[str, Any]) -> None:
    assert_no_sensitive_values(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def print_human(result: dict[str, Any]) -> None:
    assert_no_sensitive_values(result)
    print("当前结果：")
    quota = result.get("quota")
    if quota:
        print()
        print("**Codex 普通额度**")
        if quota.get("ok"):
            print(f"- 套餐类型：`{display(quota.get('plan_type'))}`")
            five = quota.get("five_hour") or {}
            seven = quota.get("seven_day") or {}
            print(f"- 5 小时额度：{display_window(five)}")
            print(f"- 7 天额度：{display_window(seven)}")
        else:
            print(f"- 查询失败：{quota.get('error')}")
            for error in quota.get("errors", []):
                print(f"  - {error}")
        if quota.get("fallback_from"):
            print(f"- live API 查询失败后回落到 local：{display(quota.get('fallback_reason'))}")

    credits = result.get("credits")
    if credits:
        print()
        print("**免费重置机会**")
        if credits.get("ok"):
            print(f"- 当前可用次数：`{display(credits.get('available_count'))}`")
            print("- 明细：")
            for credit in credits.get("credits", []):
                print(
                    f"  - 状态 `{display(credit.get('status'))}`，发放时间 `{display(credit.get('granted_at'))}`，"
                    f"过期时间 `{display(credit.get('expires_at'))}`，使用时间 `{display(credit.get('used_at'))}`"
                )
        else:
            print(f"- 查询失败：{credits.get('error')}")
            if "shape" in credits:
                print(f"- auth.json 顶层字段：`{credits['shape'].get('top_keys')}`")
                print(f"- tokens 子字段：`{credits['shape'].get('tokens_keys')}`")

    diagnose = result.get("diagnose")
    if diagnose:
        print()
        print("**诊断信息**")
        if diagnose.get("ok"):
            print(f"- 说明：{diagnose.get('note')}")
            for event in diagnose.get("events", []):
                print(f"- 事件时间 `{display(event.get('event_timestamp'))}`，来源 `{display(event.get('source'))}`")
                print(f"  - 解析后 5 小时：`{display((event.get('parsed_five_hour') or {}).get('used'))}` / `{display((event.get('parsed_five_hour') or {}).get('remaining'))}`")
                print(f"  - 解析后 7 天：`{display((event.get('parsed_seven_day') or {}).get('used'))}` / `{display((event.get('parsed_seven_day') or {}).get('remaining'))}`")
        else:
            print(f"- 查询失败：{diagnose.get('error')}")

    print()
    print("数据来源：")
    if quota:
        if quota.get("source_type") == "live_api":
            print(f"- 普通额度：live API `{quota.get('source')}`，查询时间 `{display(quota.get('event_timestamp'))}`")
        else:
            print(f"- 普通额度：local snapshot `{quota.get('source')}`，事件时间 `{display(quota.get('event_timestamp'))}`")
    if credits:
        print("- 免费重置机会：`~/.codex/auth.json` 中必要认证字段 + `rate-limit-reset-credits` 接口")
    if diagnose:
        print("- 诊断信息：`~/.codex/sessions` 中最新 `payload.rate_limits` 事件的非敏感字段")
    print()
    print("未输出 `access_token`、`refresh_token`、`account_id` 等敏感值。")


def main() -> int:
    args = parse_args()
    timezone = get_tz(args.timezone)
    result: dict[str, Any] = {}

    if args.mode in {"quota", "all"}:
        result["quota"] = quota_snapshot(args.codex_home, timezone, args.source)
    if args.mode in {"credits", "all"}:
        result["credits"] = reset_credits(args.codex_home, timezone)
    if args.mode == "diagnose":
        result["diagnose"] = diagnose_rate_limits(args.codex_home, timezone, args.limit)

    if args.json:
        print_json(result)
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
