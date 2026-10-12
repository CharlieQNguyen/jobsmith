#!/usr/bin/env bash
# Say what a jobsmith session needs and doesn't have: the CLI, and current data repo wiring.
# Silent when everything is in place. Never fails the session.
say() { printf '{"systemMessage": "%s"}\n' "$1"; }

js="$(command -v jobsmith || echo "$HOME/.local/bin/jobsmith")"
if [ ! -x "$js" ]; then
  say "jobsmith: the CLI is not installed. Run: uv tool install git+https://github.com/CharlieQNguyen/jobsmith"
  exit 0
fi

dir="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$dir/accounts.yaml" ] || exit 0   # not a data repo
# One line per thing out of step: the plugin and CLI versions, this repo's pin, its wiring.
plugin=()
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && plugin=(--plugin "$CLAUDE_PLUGIN_ROOT")
if ! out="$(cd "$dir" && "$js" init --check . "${plugin[@]}" 2>/dev/null)"; then
  # A CLI older than this plugin has no `init --check`.
  say "jobsmith: the CLI is older than the plugin. Run: uv tool upgrade jobsmith"
  exit 0
fi
[ -n "$out" ] && say "$(printf '%s' "$out" | sed 's/"/\\"/g' | awk 'NR>1{printf "\\n"}{printf "%s",$0}')"
exit 0
