#!/bin/sh
#
# Copy scripts/hooks/* into this repository's hooks directory.
# Run once per clone: sh scripts/install-hooks.sh

set -e

repo_root=$(git rev-parse --show-toplevel)
# --git-path resolves to the common hooks directory, so running this from a
# linked worktree installs the hook that every worktree actually executes.
hooks_dir=$(git rev-parse --git-path hooks)

mkdir -p "$hooks_dir"

for src in "$repo_root"/scripts/hooks/*; do
	[ -f "$src" ] || continue
	name=$(basename "$src")
	cp "$src" "$hooks_dir/$name"
	chmod +x "$hooks_dir/$name"
	echo "installed $name -> $hooks_dir/$name"
done
