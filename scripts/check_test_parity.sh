#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

base_ref="${1:-upstream/main}"
head_ref="${2:-HEAD}"

if ! git rev-parse --verify "$base_ref" > /dev/null 2>&1; then
    echo "Base ref '$base_ref' not found." >&2
    exit 1
fi

if ! git rev-parse --verify "$head_ref" > /dev/null 2>&1; then
    echo "Head ref '$head_ref' not found." >&2
    exit 1
fi

test_files=()
while IFS= read -r file; do
    if [[ -n "$file" ]]; then
        test_files+=("$file")
    fi
done < <(
    git diff --name-only "$base_ref..$head_ref" -- tests | grep -E '\.py$' || true
)

if [[ ${#test_files[@]} -eq 0 ]]; then
    echo "No changed test files under tests/ for $base_ref..$head_ref."
    exit 0
fi

tmp_output="$(mktemp)"
tmp_tests="$(mktemp)"
tmp_counts="$(mktemp)"
tmp_missing_sync="$(mktemp)"
tmp_missing_async="$(mktemp)"
tmp_payload="$(mktemp)"
trap 'rm -f "$tmp_output" "$tmp_tests" "$tmp_counts" "$tmp_missing_sync" "$tmp_missing_async" "$tmp_payload"' EXIT

echo "Running pytest on changed tests:"
printf '  - %s\n' "${test_files[@]}"

uv run pytest -vv -rA -n auto "${test_files[@]}" | tee "$tmp_output"

awk '
{
  line = $0;
  sub(/^\[[^]]+\][[:space:]]+/, "", line);
  sub(/[[:space:]]+\[[^]]+\]$/, "", line);
  if (line ~ /^(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)[[:space:]]+tests\/.*::/) {
    sub(/^(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)[[:space:]]+/, "", line);
    print line;
  } else if (line ~ /^tests\/.*::.*[[:space:]]+(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)$/) {
    sub(/[[:space:]]+(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)$/, "", line);
    print line;
  }
}
' "$tmp_output" > "$tmp_tests"

if [[ ! -s "$tmp_tests" ]]; then
    echo "No test node IDs detected in pytest output; try rerunning with -vv." >&2
    exit 1
fi

awk -v sync_file="$tmp_missing_sync" \
    -v async_file="$tmp_missing_async" \
    -v payload_file="$tmp_payload" \
    -v counts_file="$tmp_counts" '
function is_async(nodeid) {
  return (nodeid ~ /::test_.*async_/);
}
function normalize(nodeid) {
  sub(/::test_live_async_/, "::test_live_", nodeid);
  sub(/::test_async_/, "::test_", nodeid);
  return nodeid;
}
{
  total++;
  if ($0 ~ /::test_.*(payload|validation)/) {
    payload_like[$0] = 1;
  }
  if (is_async($0)) {
    async_count++;
    norm = normalize($0);
    async_norm[norm] = 1;
    async_orig[norm] = $0;
  } else {
    sync_count++;
    norm = normalize($0);
    sync_norm[norm] = 1;
    sync_orig[norm] = $0;
  }
}
END {
  missing_sync = 0;
  missing_async = 0;

  for (n in async_norm) {
    if (!(n in sync_norm)) {
      missing_sync++;
      print async_orig[n] >> sync_file;
    }
  }
  for (n in sync_norm) {
    if (!(n in async_norm)) {
      missing_async++;
      print sync_orig[n] >> async_file;
    }
  }
  payload_count = 0;
  for (t in payload_like) {
    payload_count++;
    print t >> payload_file;
  }

  print "total=" total > counts_file;
  print "sync_count=" sync_count >> counts_file;
  print "async_count=" async_count >> counts_file;
  print "missing_sync=" missing_sync >> counts_file;
  print "missing_async=" missing_async >> counts_file;
  print "payload_count=" payload_count >> counts_file;
}
' "$tmp_tests"

total=0
sync_count=0
async_count=0
missing_sync=0
missing_async=0
payload_count=0
while IFS='=' read -r key value; do
    case "$key" in
        total) total="$value" ;;
        sync_count) sync_count="$value" ;;
        async_count) async_count="$value" ;;
        missing_sync) missing_sync="$value" ;;
        missing_async) missing_async="$value" ;;
        payload_count) payload_count="$value" ;;
    esac
done < "$tmp_counts"

echo ""
echo "Test parity report"
echo "Total tests: $total"
echo "Sync tests: $sync_count"
echo "Async tests: $async_count"
echo "Missing sync counterparts: $missing_sync"
if [[ "$missing_sync" -gt 0 ]]; then
    sort "$tmp_missing_sync" | while read -r line; do
        echo "  - $line"
    done
fi
echo "Missing async counterparts: $missing_async"
if [[ "$missing_async" -gt 0 ]]; then
    sort "$tmp_missing_async" | while read -r line; do
        echo "  - $line"
    done
fi
echo "Payload/validation-style tests (name contains payload/validation): $payload_count"
if [[ "$payload_count" -gt 0 ]]; then
    sort "$tmp_payload" | while read -r line; do
        echo "  - $line"
    done
fi
