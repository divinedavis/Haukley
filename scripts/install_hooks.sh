#!/usr/bin/env bash
# Point git at the versioned hooks in .githooks/ (pre-push: gitleaks + tests/run_fast.sh).
# Run once per checkout, including worktrees.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
echo "hooks installed: $(ls .githooks | tr '\n' ' ')"
