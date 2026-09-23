#!/usr/bin/env bash
# Keep the `jobsmith` CLI installed (editable) from this checkout, reinstalling when its
# dependencies change. Cheap no-op otherwise. A data repo's SessionStart hook and git
# post-merge/post-checkout hooks call this (see `jobsmith init`).
# Prints a Claude Code {"systemMessage": ...} line only when it did something.
set -euo pipefail

pkg="$(cd "$(dirname "$0")/.." && pwd)"
uv="$(command -v uv || echo "$HOME/.local/bin/uv")"
say() { printf '{"systemMessage": "%s"}\n' "$1"; }

[ -x "$uv" ] || { say "jobsmith: uv not found — install it from https://docs.astral.sh/uv/"; exit 0; }

# Contributors' clones get the personal-data pre-commit hook.
[ "$(git -C "$pkg" config core.hooksPath 2>/dev/null)" = ".githooks" ] || git -C "$pkg" config core.hooksPath .githooks

stamp_dir="${XDG_CACHE_HOME:-$HOME/.cache}/jobsmith"
stamp="$stamp_dir/deps-$(printf '%s' "$pkg" | shasum -a 256 | cut -c1-12).sha"
want="$(cat "$pkg/pyproject.toml" "$pkg/uv.lock" | shasum -a 256 | cut -d' ' -f1)"
have="$(cat "$stamp" 2>/dev/null || true)"

if [ "$want" != "$have" ] || [ ! -x "$HOME/.local/bin/jobsmith" ]; then
  if "$uv" tool install --editable --reinstall --quiet "$pkg" >/dev/null 2>&1; then
    mkdir -p "$stamp_dir" && echo "$want" > "$stamp"
    say "jobsmith: installed/updated from $pkg"
  else
    say "jobsmith: install failed — run: uv tool install --editable --reinstall $pkg"
  fi
fi
