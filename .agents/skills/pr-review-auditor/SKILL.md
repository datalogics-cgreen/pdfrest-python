---
name: pr-review-auditor
description: Review the currently checked-out PR by discovering its upstream base branch with GitHub CLI, diffing base..HEAD, and performing a correctness-first code review that enforces repository policy with special priority on *GUIDELINES*.md rules and then AGENTS.md. Use when asked to do a full PR review, /review-style audit, commit-range quality check, or policy-compliance review of branch changes.
---

# PR Review Auditor

## Overview

Review branch changes from PR base to `HEAD` with findings-first output.
Prioritize correctness risks, then CI regressions, then test gaps, and enforce
policy precedence: `*GUIDELINES*.md` before `AGENTS.md`.

## Workflow

1. Collect context from the active branch. Run
   `.agents/skills/pr-review-auditor/scripts/collect_pr_context.sh` from repo
   root to detect:

- checked-out branch,
- PR number and base branch (via `gh pr view`),
- merge-base commit,
- review range (`origin/<base>..HEAD`),
- changed files,
- available policy files (`*GUIDELINES*.md`, `AGENTS.md`).

2. Inspect commits and patches in range. Run
   `.agents/skills/pr-review-auditor/scripts/review_range.sh` with the range
   from step 1. This prints:

- commits with full messages (`git log --format=fuller`),
- per-commit changed files,
- unified patches for detailed behavior review.

3. Run a three-pass policy protocol (Markdown-only). Pass 1: Rule extraction

- Read all `*GUIDELINES*.md` files first, then `AGENTS.md`.
- Extract rules section-by-section by heading. For each heading, list actionable
  rules before moving to the next heading.
- Extract every actionable rule into a numbered list with source citation.
- Keep wording close to source text and avoid merging unrelated rules.
- Minimum extraction floors:
  - `TESTING_GUIDELINES.md`: at least 20 rules unless a heading-by-heading audit
    proves fewer.
  - `AGENTS.md`: at least 15 rules unless a heading-by-heading audit proves
    fewer.
  - If below floor, include an explicit justification section that names each
    heading and why no additional actionable rule exists. Pass 2: Evidence
    mapping
- For each extracted rule, assign `pass`, `fail`, or `n/a`.
- Provide concrete evidence (`file:line`, command output, or explicit absence).
- If rules conflict, cite both and follow `*GUIDELINES*.md`. Pass 3: Adversarial
  gap check
- Re-read diffs and policy files only to find missed rules/findings.
- Add new findings only when they include new source citations and evidence.
- Require at least 5 "candidate missed rules" per policy file during this pass,
  then mark each as `new rule` or `duplicate` with rationale.

4. Perform review in severity order.

- Correctness/behavioral regressions.
- CI and workflow regressions.
- Test gaps or weak assertions.
- Secondary maintainability/style concerns.

5. Produce findings-first output. List issues with file/line references and
   policy citation when applicable. Separate policy findings into two explicit
   sections:

- `GUIDELINES findings`
- `AGENTS findings`

6. Provide a remediation plan. Include:

- ordered fix plan,
- tests to run and why,
- tests not run and why,
- assumptions and open questions.

## Output Requirements

- Findings first, ordered by severity.
- Include commit-message quality notes when relevant.
- Cite exact paths and lines for each finding.
- Include `files reviewed`, `tests run`, and `tests not run`.
- If no findings exist, state that explicitly and list residual risks.
- Include a `Rule Coverage Matrix` section in Markdown.
- Do not mark the review complete until every extracted rule has a status and
  evidence.
- Do not emit internal script-path fallback chatter; run the canonical
  `.agents/skills/pr-review-auditor/scripts/*` paths directly.
- Include a `Rule Extraction Summary` with:
  - total rules per source file,
  - per-heading rule counts,
  - whether extraction floors were met,
  - explicit justification if any floor was not met.

## Rule Coverage Matrix Template

Use this exact table shape:

| Rule ID | Source                | Rule Summary | Status (pass/fail/n-a) | Evidence           |
| ------- | --------------------- | ------------ | ---------------------- | ------------------ |
| G-001   | TESTING_GUIDELINES.md | ...          | pass                   | tests/test_x.py:42 |
| A-001   | AGENTS.md             | ...          | fail                   | src/module.py:87   |

## Trigger Examples

- "Figure out this PR's base branch and do a /review from base to HEAD."
- "Audit all commits in this branch and check AGENTS + GUIDELINES compliance."
- "Review patches in this PR and give me a fix plan with test gaps."

## Resources

- `.agents/skills/pr-review-auditor/scripts/collect_pr_context.sh`: derive PR
  base/range and policy file inventory.
- `.agents/skills/pr-review-auditor/scripts/review_range.sh`: print full commit
  messages and patches for a range.
- `references/review-checklist.md`: compact review checklist and severity
  rubric.
