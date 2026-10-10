#!/usr/bin/env bash
# Fails when a Freya API key or this team's bank key is in a staged file. Installed as .git/hooks/pre-commit.
set -u
cd "$(git rev-parse --show-toplevel)"
status=0
# real keys start with fak_; the docs use placeholders such as fak_your_key, which are fine
hits=$(git grep --cached -nI -E 'fak_[A-Za-z0-9_-]{8,}' -- . | grep -v 'fak_your' || true)
if [ -n "$hits" ]; then
  echo "A Freya API key is in a staged file. Remove it before committing:"; echo "$hits"; status=1
fi
if [ -f env.sh ]; then
  key=$(grep -E '^export FREYA_BANK_TEAM_KEY=' env.sh | cut -d= -f2- | awk '{print $1}' | tr -d "\"'")
  if [ -n "$key" ] && [ "$key" != "pick-any-secret-of-16-or-more-characters" ]; then
    hits=$(git grep --cached -nIF "$key" -- . || true)
    if [ -n "$hits" ]; then echo "The team key is in a staged file. Remove it before committing:"; echo "$hits"; status=1; fi
  fi
fi
[ $status -eq 0 ] && echo "check_secrets: no keys in staged files"
exit $status
