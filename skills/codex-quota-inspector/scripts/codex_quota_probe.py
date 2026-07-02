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


RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"
SECRET_VALUE_MARKERS = ("eyJ", "Bearer ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["quota", "credits", "all"], help="Query mode")
    parser.add_argument("--timezone", default=None, help="IANA timezone, e.g. Asia/Shanghai")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--codex-home", default=os.path.expanduser("~/.codex"))
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


def latest_rate_limits(codex_home: str, timezone: dt.tzinfo | None) -> dict[str, Any]:
    sessions_dir = os.path.join(codex_home, "sessions")
    paths = glob.glob(os.path.join(sessions_dir, "**", "*.jsonl"), recursive=True)
    latest: tuple[str, str, dict[str, Any]] | None = None

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
                    if latest is None or timestamp > latest[0]:
                        latest = (timestamp, path, payload)
        except OSError:
            continue

    if latest is None:
        return {"ok": False, "error": "未找到 payload.rate_limits 事件", "source": sessions_dir}

    timestamp, source, payload = latest
    rate_limits = payload.get("rate_limits")
    if not isinstance(rate_limits, dict):
        return {
            "ok": False,
            "error": "payload.rate_limits 不是对象",
            "event_timestamp": format_time(timestamp, timezone),
            "source": source,
        }

    primary = rate_limits.get("primary") if isinstance(rate_limits.get("primary"), dict) else {}
    secondary = rate_limits.get("secondary") if isinstance(rate_limits.get("secondary"), dict) else {}

    return {
        "ok": True,
        "event_timestamp": format_time(timestamp, timezone),
        "source": source,
        "plan_type": rate_limits.get("plan_type"),
        "five_hour": parse_window(primary, timezone),
        "seven_day": parse_window(secondary, timezone),
    }


def parse_window(window: dict[str, Any], timezone: dt.tzinfo | None) -> dict[str, Any]:
    used = pick(window, "used", "used_count", "current", "used_percent")
    remaining = pick(window, "remaining", "remaining_count")
    if remaining is None and isinstance(used, (int, float)) and "used_percent" in window:
        remaining = max(0, 100 - used)
    return {
        "used": format_percent_if_needed(used, "used_percent" in window),
        "remaining": format_percent_if_needed(remaining, "used_percent" in window),
        "reset_at": format_time(pick(window, "resets_at", "reset_at", "resetAt", "reset_time"), timezone),
        "window_minutes": window.get("window_minutes"),
    }


def pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def format_percent_if_needed(value: Any, is_percent: bool) -> Any:
    if value is None:
        return None
    if is_percent and isinstance(value, (int, float)):
        return f"{value:g}%"
    return value


def display(value: Any) -> str:
    return "null" if value is None else str(value)


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


def reset_credits(codex_home: str, timezone: dt.tzinfo | None) -> dict[str, Any]:
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

    request = urllib.request.Request(
        RESET_CREDITS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "OpenAI-Account": str(account_id),
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
            print(f"- 5 小时额度：已用 `{display(five.get('used'))}`，剩余 `{display(five.get('remaining'))}`，重置时间 `{display(five.get('reset_at'))}`")
            print(f"- 7 天额度：已用 `{display(seven.get('used'))}`，剩余 `{display(seven.get('remaining'))}`，重置时间 `{display(seven.get('reset_at'))}`")
        else:
            print(f"- 查询失败：{quota.get('error')}")

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

    print()
    print("数据来源：")
    if quota:
        print(f"- 普通额度：`{quota.get('source')}` 最新 `payload.rate_limits` 事件")
    if credits:
        print("- 免费重置机会：`~/.codex/auth.json` 中必要认证字段 + `rate-limit-reset-credits` 接口")
    print()
    print("未输出 `access_token`、`refresh_token`、`account_id` 等敏感值。")


def main() -> int:
    args = parse_args()
    timezone = get_tz(args.timezone)
    result: dict[str, Any] = {}

    if args.mode in {"quota", "all"}:
        result["quota"] = latest_rate_limits(args.codex_home, timezone)
    if args.mode in {"credits", "all"}:
        result["credits"] = reset_credits(args.codex_home, timezone)

    if args.json:
        print_json(result)
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
