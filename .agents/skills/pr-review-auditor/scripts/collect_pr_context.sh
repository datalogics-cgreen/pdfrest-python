#!/usr/bin/env bash
set -euo pipefail

branch="$(git rev-parse --abbrev-ref HEAD)"
base_remote="origin"
if git remote get-url upstream > /dev/null 2>&1; then
    base_remote="upstream"
fi

context_source="gh-pr-view"
pr_number="N/A"
head_ref="${branch}"
base_ref=""
pr_json=""
gh_error=""

if command -v gh > /dev/null 2>&1 && command -v jq > /dev/null 2>&1; then
    gh_error_file="$(mktemp)"
    if ! pr_json="$(gh pr view --json number,baseRefName,headRefName 2> "${gh_error_file}")"; then
        pr_json=""
    fi
    if [[ -z "${pr_json}" ]]; then
        gh_error="$(< "${gh_error_file}")"
    fi
    rm -f "${gh_error_file}"
fi

if [[ -n "${pr_json}" && "${pr_json}" != "null" ]]; then
    pr_number="$(jq -r '.number' <<< "${pr_json}")"
    base_ref="$(jq -r '.baseRefName' <<< "${pr_json}")"
    head_ref="$(jq -r '.headRefName' <<< "${pr_json}")"
else
    context_source="remote-head-fallback"
    remote_head_ref="$(git symbolic-ref --quiet --short "refs/remotes/${base_remote}/HEAD" || true)"
    if [[ -z "${remote_head_ref}" ]]; then
        echo "error: unable to derive base branch from refs/remotes/${base_remote}/HEAD" >&2
        echo "hint: run 'git remote set-head ${base_remote} --auto' and retry" >&2
        if [[ -n "${gh_error}" ]]; then
            echo "gh pr view: ${gh_error}" >&2
        fi
        exit 1
    fi
    base_ref="${remote_head_ref#"${base_remote}"/}"
    if [[ -n "${gh_error}" ]]; then
        echo "warning: gh pr view failed; using ${base_remote}/HEAD fallback" >&2
        echo "gh pr view: ${gh_error}" >&2
    fi
fi

fetch_error_file="$(mktemp)"
if ! git fetch --quiet "${base_remote}" "${base_ref}" 2> "${fetch_error_file}"; then
    if git rev-parse --verify --quiet "${base_remote}/${base_ref}" > /dev/null; then
        echo "warning: git fetch failed; using cached ${base_remote}/${base_ref}" >&2
        cat "${fetch_error_file}" >&2
    else
        echo "error: unable to fetch ${base_remote}/${base_ref} and no local cached ref exists" >&2
        cat "${fetch_error_file}" >&2
        rm -f "${fetch_error_file}"
        exit 1
    fi
fi
rm -f "${fetch_error_file}"

merge_base="$(git merge-base "${base_remote}/${base_ref}" HEAD)"
review_range="${merge_base}..HEAD"

echo "CONTEXT_SOURCE=${context_source}"
echo "PR_NUMBER=${pr_number}"
echo "CURRENT_BRANCH=${branch}"
echo "PR_HEAD_BRANCH=${head_ref}"
echo "PR_BASE_BRANCH=${base_ref}"
echo "PR_BASE_REMOTE=${base_remote}"
echo "MERGE_BASE=${merge_base}"
echo "REVIEW_RANGE=${review_range}"
echo

echo "CHANGED_FILES:"
git diff --name-only "${review_range}"
echo

echo "POLICY_FILES:"
find . -type f \( -name '*GUIDELINES*.md' -o -name 'AGENTS.md' \) | sort
