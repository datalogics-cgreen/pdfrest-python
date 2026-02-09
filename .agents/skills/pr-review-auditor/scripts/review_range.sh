#!/usr/bin/env bash
set -euo pipefail

range="${1:-}"
if [[ -z "${range}" ]]; then
    echo "usage: $(basename "$0") <git-range>" >&2
    echo "example: $(basename "$0") origin/main..HEAD" >&2
    exit 1
fi

echo "=== RANGE ==="
echo "${range}"
echo

echo "=== COMMITS (full messages) ==="
git log --format=fuller "${range}"
echo

echo "=== COMMIT FILE SUMMARIES ==="
git log --name-status --format='commit %H%nAuthor: %an <%ae>%nDate: %ad%n%n%s%n%b' "${range}"
echo

echo "=== PATCHES ==="
git log --patch --stat "${range}"
