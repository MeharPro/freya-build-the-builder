#!/bin/bash
# Paste the new OpenAI key when asked (nothing is echoed). Writes it into env.sh (gitignored) and copies the
# `OPENAI_API_KEY=...` line to the clipboard for the cloud environment's variables box.
cd "$(dirname "$0")/.." || exit 1
read -r -s -p "Paste the OpenAI key and press Enter: " KEY; echo
KEY="${KEY//[$'\r\n\t ']/}"
case "$KEY" in sk-*) ;; *) echo "that does not look like an OpenAI key (expected sk-...)"; exit 1;; esac
if grep -q "OPENAI_API_KEY=" env.sh; then
  sed -i '' "s|^.*OPENAI_API_KEY=.*|export OPENAI_API_KEY=${KEY}|" env.sh
else
  printf 'export OPENAI_API_KEY=%s\n' "$KEY" >> env.sh
fi
grep -q "^export OPENAI_API_KEY=${KEY}$" env.sh && echo "env.sh: OPENAI_API_KEY set (ends with ...${KEY: -4})" || { echo "env.sh: write failed"; exit 1; }
printf 'OPENAI_API_KEY=%s' "$KEY" | pbcopy && echo "clipboard: OPENAI_API_KEY=... copied for the cloud environment variables box"
