#!/usr/bin/env bash
# Print env.sh in the .env format the Claude Code cloud environment dialog expects (KEY=value, one per line,
# no `export`, no comments). Usage:  tools/env_to_cloud.sh            # prints to the terminal
#                                     tools/env_to_cloud.sh | pbcopy   # copies it, ready to paste into the dialog
set -euo pipefail
f="${1:-$(dirname "$0")/../env.sh}"
[ -f "$f" ] || { echo "no such file: $f" >&2; exit 1; }
# keep `export KEY=value` lines, drop the word export, strip a trailing comment, trim surrounding quotes and spaces
sed -nE 's/^[[:space:]]*export[[:space:]]+([A-Za-z_][A-Za-z0-9_]*)=(.*)$/\1=\2/p' "$f" \
  | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' \
  | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)="(.*)"$/\1=\2/; s/^([A-Za-z_][A-Za-z0-9_]*)='"'"'(.*)'"'"'$/\1=\2/'
