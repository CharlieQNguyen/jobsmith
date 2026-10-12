#!/usr/bin/env bash
# The plugin is how jobsmith is installed and updated. It carries jobsmith's source, so this
# hook installs the `jobsmith` CLI from the plugin's own copy whenever the two versions differ:
# updating the plugin updates the CLI. An editable install (someone developing jobsmith) is
# left alone and reported instead.
#
# Then it says what else is out of step in a data repo: its recorded version and its wiring.
# Prints one {"systemMessage": ...} line, or nothing when everything is in place. Never fails
# the session.
lines=()
finish() {
  [ ${#lines[@]} -eq 0 ] && exit 0
  msg="$(printf '%s\n' "${lines[@]}" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'NR>1{printf "\\n"}{printf "%s",$0}')"
  printf '{"systemMessage": "%s"}\n' "$msg"
  exit 0
}

root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
want="$(tr -d '\n' < "$root/.claude-plugin/plugin.json" | sed -n 's/.*"version" *: *"\([^"]*\)".*/\1/p')"
uv="$(command -v uv || echo "$HOME/.local/bin/uv")"
js="$(command -v jobsmith || echo "$HOME/.local/bin/jobsmith")"
have="$([ -x "$js" ] && "$js" --version 2>/dev/null)"

if [ "$have" != "$want" ]; then
  receipt="$([ -x "$uv" ] && "$uv" tool dir 2>/dev/null)/jobsmith/uv-receipt.toml"
  if [ -n "$have" ] && grep -q 'editable *=' "$receipt" 2>/dev/null; then
    : # a development install: `init --check` below reports the difference
  elif [ ! -x "$uv" ]; then
    lines+=("jobsmith: the plugin needs uv to install the jobsmith command: https://docs.astral.sh/uv/")
    finish
  elif "$uv" tool install --reinstall --quiet "$root" >/dev/null 2>&1; then
    js="$(command -v jobsmith || echo "$HOME/.local/bin/jobsmith")"
    lines+=("jobsmith: installed the jobsmith command ${want} to match the plugin${have:+ (was $have)}")
  else
    lines+=("jobsmith: could not install the jobsmith command. Run: uv tool install --reinstall \"$root\"")
    finish
  fi
fi

dir="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$dir/accounts.yaml" ] || finish   # not a data repo
# One line per thing out of step: the plugin and CLI versions, this repo's pin, its wiring.
if out="$(cd "$dir" && "$js" init --check . --plugin "$root" 2>/dev/null)"; then
  while IFS= read -r line; do [ -n "$line" ] && lines+=("$line"); done <<< "$out"
else
  lines+=("jobsmith: the jobsmith command could not check this data repo. Run: jobsmith init --check .")
fi
finish
