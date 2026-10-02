#!/usr/bin/env bash
# Every fast automated test in the repo, in one command (about 10 s):
#   1. TypeScript typecheck of the React Native TV app (tsc --noEmit)
#   2. Jest (__tests__/, RN catalog/history/App)
#   3. Python checks (tests/test_*.py via tests/run_unit.py: catalog on every platform,
#      haukley.com pages)
#   4. Roku BrightScript unit tests (roku/tests/*_test.brs in the brs-node emulator;
#      brs-cli always exits 0, so this fails on any FAIL line or a missing DONE line)
# Run by .githooks/pre-push and scripts/deploy_web.sh. Slow suites that need a browser,
# simulator or device are NOT here; see the Tests section of CLAUDE.md.
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0
step() { printf '%-28s' "$1"; shift; if out=$("$@" 2>&1); then echo ok; else echo FAIL; echo "$out" | tail -40; fail=1; fi; }

step "typecheck (tsc)" ./node_modules/.bin/tsc --noEmit
step "jest" ./node_modules/.bin/jest --ci --silent
step "python (tests/run_unit.py)" python3 tests/run_unit.py
roku() {
  cd roku
  local f out
  for f in tests/*_test.brs; do
    out=$(npx --prefer-offline -y -p brs-node@2.6.0 brs-cli components/Content.brs "$f" 2>&1)
    echo "$out" | grep -E '^(PASS|FAIL) '
    if echo "$out" | grep -q '^FAIL '; then return 1; fi
    if ! echo "$out" | grep -q 'TESTS DONE'; then echo "$f did not finish"; return 1; fi
  done
}
step "roku (brs-node)" roku
exit $fail
