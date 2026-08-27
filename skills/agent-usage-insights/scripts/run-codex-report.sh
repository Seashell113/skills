#!/usr/bin/env bash
set -euo pipefail

codex_home_dir="${AGENT_USAGE_INSIGHTS_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}"
tool_dir="${AGENT_USAGE_INSIGHTS_TOOL_DIR:-}"
if [ -z "$tool_dir" ]; then
  for candidate in \
    "$codex_home_dir/tools/agent-usage-insights" \
    "$HOME/workspace/ai/ai-workspace/system/tools/agent-usage-insights" \
    "$HOME/workspace/ai/ai-workspace/tools/agent-usage-insights"
  do
    if [ -d "$candidate/src/agent_usage_insights" ]; then
      tool_dir="$candidate"
      break
    fi
  done
fi

if [ -z "$tool_dir" ] || [ ! -d "$tool_dir/src/agent_usage_insights" ]; then
  echo "agent-usage-insights tool directory not found; set AGENT_USAGE_INSIGHTS_TOOL_DIR" >&2
  exit 1
fi

report_path="${AGENT_USAGE_INSIGHTS_REPORT:-$codex_home_dir/insights/report.html}"
context_path="${AGENT_USAGE_INSIGHTS_CONTEXT:-$codex_home_dir/insights/llm-context.json}"
analysis_path="${AGENT_USAGE_INSIGHTS_ANALYSIS:-$codex_home_dir/insights/agent-analysis.json}"
max_sessions="${AGENT_USAGE_INSIGHTS_MAX_SESSIONS:-50}"
include_transcripts="${AGENT_USAGE_INSIGHTS_INCLUDE_TRANSCRIPTS:-0}"
use_analysis="${AGENT_USAGE_INSIGHTS_USE_ANALYSIS:-0}"

python_bin="${AGENT_USAGE_INSIGHTS_PYTHON:-}"
if [ -z "$python_bin" ] && [ -x "$tool_dir/.venv/bin/python" ]; then
  python_bin="$tool_dir/.venv/bin/python"
fi
if [ -z "$python_bin" ] && command -v python3.11 >/dev/null 2>&1; then
  python_bin="$(command -v python3.11)"
fi
if [ -z "$python_bin" ] && command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
fi
if [ -z "$python_bin" ]; then
  echo "Python 3.11+ not found; set AGENT_USAGE_INSIGHTS_PYTHON" >&2
  exit 1
fi

args=(
  -m agent_usage_insights
  --codex-home "$codex_home_dir"
  --output "$report_path"
  --llm-context-output "$context_path"
  --llm-context-max-sessions "$max_sessions"
)

if [ "$include_transcripts" = "1" ]; then
  args+=(--include-transcript-excerpts)
fi
if [ "$use_analysis" = "1" ]; then
  if [ ! -f "$analysis_path" ]; then
    echo "analysis file not found: $analysis_path" >&2
    exit 1
  fi
  args+=(--analysis-input "$analysis_path")
fi
if [ -n "${AGENT_USAGE_INSIGHTS_START:-}" ]; then
  args+=(--start "$AGENT_USAGE_INSIGHTS_START")
fi
if [ -n "${AGENT_USAGE_INSIGHTS_END:-}" ]; then
  args+=(--end "$AGENT_USAGE_INSIGHTS_END")
fi
if [ -n "${AGENT_USAGE_INSIGHTS_TIMEZONE:-}" ]; then
  args+=(--timezone "$AGENT_USAGE_INSIGHTS_TIMEZONE")
fi
if [ -n "${AGENT_USAGE_INSIGHTS_SNAPSHOT_MANIFEST:-}" ]; then
  args+=(--snapshot-manifest "$AGENT_USAGE_INSIGHTS_SNAPSHOT_MANIFEST")
fi
if [ "${AGENT_USAGE_INSIGHTS_INCLUDE_ARCHIVED:-0}" = "1" ]; then
  args+=(--include-archived)
fi
if [ "${AGENT_USAGE_INSIGHTS_ALLOW_UNFROZEN_ARCHIVED:-0}" = "1" ]; then
  args+=(--allow-unfrozen-archived)
fi
if [ "${AGENT_USAGE_INSIGHTS_INCLUDE_INTERNAL:-0}" = "1" ]; then
  args+=(--include-internal)
fi
if [ -n "${AGENT_USAGE_INSIGHTS_METRICS:-}" ]; then
  args+=(--metrics-output "$AGENT_USAGE_INSIGHTS_METRICS")
fi
if [ -n "${AGENT_USAGE_INSIGHTS_CHATGPT_TASK_IDS:-}" ]; then
  args+=(--chatgpt-task-ids "$AGENT_USAGE_INSIGHTS_CHATGPT_TASK_IDS")
fi

args+=("$@")
PYTHONPATH="$tool_dir/src${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" "${args[@]}"
