# PR Review Checklist

## Policy Precedence

1. `*GUIDELINES*.md` rules are highest-priority compliance checks.
2. `AGENTS.md` rules are required secondary checks.
3. If rules conflict, cite both files and follow `*GUIDELINES*.md`.

## Review Scope

- Determine PR base branch and audit `origin/<base>..HEAD`.
- Review full commit messages, changed files, and relevant patches.
- Focus on behavior, CI impact, tests, then style.

## Three-Pass Completeness Protocol

1. Rule extraction pass:

- Enumerate every actionable rule from `*GUIDELINES*.md`, then `AGENTS.md`.
- Extract heading-by-heading and record per-heading counts.
- Assign stable rule IDs (for example `G-001`, `A-001`).
- Meet extraction floors unless explicitly justified:
  - `TESTING_GUIDELINES.md`: >= 20 rules.
  - `AGENTS.md`: >= 15 rules.
  - If below floor, justify heading-by-heading why no additional actionable
    rules exist.

2. Evidence mapping pass:

- Map every rule to `pass`, `fail`, or `n/a`.
- Attach evidence for every status (path/line or concrete command output).

3. Gap pass:

- Re-check changed files and policy text for missing rules/findings.
- Add only findings backed by new source citations and evidence.
- Generate at least 5 missed-rule candidates per policy file, then classify each
  as `new rule` or `duplicate` with rationale.

## Severity Order

1. Correctness risk: behavior bug, data loss, runtime failure, API mismatch.
2. CI/workflow regression: broken matrix, wrong triggers, missing job parity.
3. Test gap: missing or weak coverage for changed behavior.
4. Maintainability/style: readability or consistency issues with low break risk.

## Mandatory Output Sections

- Findings (ordered by severity, each with path/line evidence).
- Rule Coverage Matrix (every extracted rule must be represented).
- Rule Extraction Summary (totals per file, per-heading counts, floors met/not
  met).
- GUIDELINES findings.
- AGENTS findings.
- Open questions and assumptions.
- Remediation plan with validation steps.
- Files reviewed.
- Tests run.
- Tests not run and why.

## Completion Gate

- The review is incomplete if any extracted rule is missing from the matrix.
- The review is incomplete if any matrix row lacks status or evidence.
- The review is incomplete if extraction floors are missed without explicit
  heading-by-heading justification.
