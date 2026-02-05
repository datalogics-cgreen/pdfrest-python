#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FunctionCoverage:
    file: str
    function: str
    percent_covered: float
    covered_lines: int
    num_statements: int


def _parse_classes(values: Iterable[str]) -> list[str]:
    classes: list[str] = []
    for value in values:
        if not value:
            continue
        for item in value.split(","):
            item = item.strip()
            if item:
                classes.append(item)
    return classes


def _load_coverage(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        message = f"Coverage JSON not found: {path}"
        raise SystemExit(message) from None
    except json.JSONDecodeError as exc:
        message = f"Invalid coverage JSON: {exc}"
        raise SystemExit(message) from exc

    if not isinstance(data, dict) or "files" not in data:
        message = "Coverage JSON missing 'files' data."
        raise SystemExit(message)
    return data


def _match_class(function_name: str, classes: Iterable[str]) -> str | None:
    for class_name in classes:
        prefix = f"{class_name}."
        if function_name.startswith(prefix):
            return class_name
    return None


def _collect_function_coverage(
    data: dict, classes: list[str]
) -> tuple[list[FunctionCoverage], set[str]]:
    results: list[FunctionCoverage] = []
    matched_classes: set[str] = set()

    for file_name, file_info in data.get("files", {}).items():
        functions = file_info.get("functions") or {}
        for function_name, function_info in functions.items():
            if not function_name or "." not in function_name:
                continue
            class_name = _match_class(function_name, classes)
            if not class_name:
                continue

            summary = function_info.get("summary") or {}
            percent = summary.get("percent_covered")
            covered_lines = summary.get("covered_lines")
            num_statements = summary.get("num_statements")
            if percent is None or covered_lines is None or num_statements is None:
                continue

            matched_classes.add(class_name)
            results.append(
                FunctionCoverage(
                    file=file_name,
                    function=function_name,
                    percent_covered=float(percent),
                    covered_lines=int(covered_lines),
                    num_statements=int(num_statements),
                )
            )

    return results, matched_classes


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check function coverage for methods in specified classes using coverage.py JSON data."
        )
    )
    parser.add_argument("coverage_json", type=Path, help="Path to coverage.json")
    parser.add_argument(
        "--class",
        dest="classes",
        action="append",
        default=[],
        help="Class name to check (repeatable).",
    )
    parser.add_argument(
        "--classes",
        dest="classes_csv",
        default="",
        help="Comma-separated class names to check.",
    )
    parser.add_argument(
        "--fail-under",
        "--min-coverage",
        dest="fail_under",
        type=float,
        required=True,
        help="Minimum coverage percentage required for each function.",
    )
    parser.add_argument(
        "--markdown-report",
        dest="markdown_report",
        type=Path,
        default=None,
        help="Write a markdown report to the given path.",
    )
    return parser.parse_args()


def _print_summary(
    classes: list[str],
    threshold: float,
    functions: list[FunctionCoverage],
    missing_classes: list[str],
    failures: list[FunctionCoverage],
) -> None:
    print(f"Minimum required coverage: {threshold:.2f}%")
    print(f"Classes checked: {', '.join(classes)}")
    print(f"Functions checked: {len(functions)}")

    if missing_classes:
        print("Classes with no discovered functions:")
        for cls in missing_classes:
            print(f"- {cls}")

    if failures:
        print("Functions with insufficient coverage:")
        for fn in sorted(failures, key=lambda item: (item.file, item.function)):
            print(
                f"- {fn.file} :: {fn.function} -> {fn.percent_covered:.2f}% "
                f"({fn.covered_lines}/{fn.num_statements} lines)"
            )


def _build_report_lines(
    classes: list[str],
    threshold: float,
    functions: list[FunctionCoverage],
    missing_classes: list[str],
    failures: list[FunctionCoverage],
) -> list[str]:
    report_lines = [
        "# Function Coverage Report",
        "",
        f"- Minimum required coverage: {threshold:.2f}%",
        f"- Classes checked: {', '.join(classes)}",
        f"- Functions checked: {len(functions)}",
    ]
    if missing_classes:
        report_lines.append("- Classes with no discovered functions:")
        report_lines.extend(f"  - {cls}" for cls in missing_classes)
    if failures:
        report_lines.append("- Functions with insufficient coverage:")
        report_lines.extend(
            f"  - {fn.file} :: {fn.function} -> {fn.percent_covered:.2f}% "
            f"({fn.covered_lines}/{fn.num_statements} lines)"
            for fn in sorted(failures, key=lambda item: (item.file, item.function))
        )
    else:
        report_lines.append("- All checked functions meet the coverage threshold.")
    return report_lines


def _write_markdown_report(path: Path, report_lines: list[str]) -> None:
    path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()

    classes = _parse_classes([*args.classes, args.classes_csv])
    if not classes:
        print("No classes specified. Use --class or --classes.", file=sys.stderr)
        return 2

    data = _load_coverage(args.coverage_json)
    functions, matched_classes = _collect_function_coverage(data, classes)

    missing_classes = [cls for cls in classes if cls not in matched_classes]
    if not functions:
        print("No functions found for the requested classes.")

    threshold = args.fail_under
    failures: list[FunctionCoverage] = [
        fn for fn in functions if fn.percent_covered + 1e-9 < threshold
    ]

    _print_summary(classes, threshold, functions, missing_classes, failures)

    if args.markdown_report:
        report_lines = _build_report_lines(
            classes, threshold, functions, missing_classes, failures
        )
        _write_markdown_report(args.markdown_report, report_lines)

    if failures or missing_classes:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
