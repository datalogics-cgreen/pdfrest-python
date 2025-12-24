from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import nox
from packaging.specifiers import SpecifierSet
from packaging.version import Version

nox.options.default_venv_backend = "uv"

python_versions = ("3.10", "3.11", "3.12", "3.13", "3.14")
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_EXAMPLE_PYTHON = "3.11"
EXAMPLES_DIR = PROJECT_ROOT / "examples"


@dataclass(frozen=True)
class ExampleScript:
    base: Path
    overrides: dict[str, Path]

    def select_for_python(self, python_version: str) -> Path:
        interpreter = Version(python_version)
        for version_str, script_path in sorted(
            self.overrides.items(), key=lambda item: Version(item[0])
        ):
            if interpreter <= Version(version_str):
                return script_path
        return self.base


def _is_override_dir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith("python-")


def _discover_example_scripts() -> list[ExampleScript]:
    examples: list[ExampleScript] = []
    if not EXAMPLES_DIR.exists():
        return examples

    for script in sorted(EXAMPLES_DIR.rglob("*.py")):
        relative_parts = script.relative_to(EXAMPLES_DIR).parts
        if not relative_parts:
            continue
        if relative_parts[0] == "resources":
            continue
        if any(part.startswith("python-") for part in relative_parts):
            continue

        parent = script.parent
        overrides: dict[str, Path] = {}
        for override_dir in parent.iterdir():
            if not _is_override_dir(override_dir):
                continue
            override_script = override_dir / script.name
            if override_script.exists():
                overrides[override_dir.name.removeprefix("python-")] = override_script

        examples.append(ExampleScript(base=script, overrides=overrides))

    return examples


EXAMPLE_SCRIPTS = _discover_example_scripts()


@dataclass(frozen=True)
class ScriptMetadata:
    requires_python: str | None
    dependencies: tuple[str, ...]


@cache
def _load_script_metadata(script: Path) -> ScriptMetadata:
    requires_python: str | None = None
    dependencies: tuple[str, ...] = ()
    if not script.exists():
        return ScriptMetadata(requires_python, dependencies)

    lines = script.read_text().splitlines()
    if not lines or lines[0].strip() != "# /// script":
        return ScriptMetadata(requires_python, dependencies)

    block: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "# ///":
            break
        if stripped.startswith("# "):
            block.append(stripped[2:])
        else:
            break

    metadata: dict[str, str] = {}
    for entry in block:
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        metadata[key.strip()] = value.strip()

    if raw := metadata.get("requires-python"):
        requires_python = ast.literal_eval(raw)
    if raw := metadata.get("dependencies"):
        dependencies = tuple(ast.literal_eval(raw))

    return ScriptMetadata(requires_python, dependencies)


def _script_supports_python(script: Path, python_version: str) -> bool:
    metadata = _load_script_metadata(script)
    if not metadata.requires_python:
        return True
    spec = SpecifierSet(metadata.requires_python)
    return Version(python_version) in spec


def _collect_script_dependencies(scripts: Iterable[Path]) -> list[str]:
    deps: set[str] = set()
    for script in scripts:
        metadata = _load_script_metadata(script)
        for dependency in metadata.dependencies:
            if dependency.split("[", 1)[0] == "pdfrest":
                continue
            deps.add(dependency)
    return sorted(deps)


def _scripts_for_python(python_version: str) -> list[Path]:
    selected: list[Path] = []
    for example in EXAMPLE_SCRIPTS:
        script = example.select_for_python(python_version)
        if _script_supports_python(script, python_version):
            selected.append(script)
    return sorted(selected)


def _preferred_python_for_script(script: Path) -> str:
    metadata = _load_script_metadata(script)
    if not metadata.requires_python:
        return DEFAULT_EXAMPLE_PYTHON

    spec = SpecifierSet(metadata.requires_python)
    for version in python_versions:
        if Version(version) in spec:
            return version
    return DEFAULT_EXAMPLE_PYTHON


def _infer_python_version_from_path(script: Path) -> str | None:
    for parent in script.parents:
        name = parent.name
        if name.startswith("python-"):
            _, _, version = name.partition("-")
            return version
    return None


@nox.session(name="tests", python=python_versions, reuse_venv=True)
def tests(session: nox.Session) -> None:
    # Define only custom flags
    parser = argparse.ArgumentParser(add_help=False)
    _ = parser.add_argument("--no-parallel", action="store_true")
    _ = parser.add_argument(
        "-n", "--workers", "--numprocesses"
    )  # e.g., -n 4 to set workers
    custom, remaining = parser.parse_known_args(session.posargs)

    pytest_args = list(remaining)

    # Default to parallel unless disabled or overridden
    if custom.no_parallel:
        pass
    elif custom.workers:
        pytest_args[:0] = ["-n", custom.workers, "--maxschedchunk", "2"]
    else:
        pytest_args[:0] = ["-n", "8", "--maxschedchunk", "2"]

    _ = session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group=dev",
        "--reinstall-package=pdfrest",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    _ = session.run(
        "pytest",
        "--cov=pdfrest",
        "--cov-report=term-missing",
        *pytest_args,
    )


@nox.session(name="examples", python=python_versions, reuse_venv=True)
def run_examples(session: nox.Session) -> None:
    """Execute example scripts across supported interpreters."""
    if not session.python:
        session.error("Interpreter selection is required for the examples session.")

    if type(session.python) is not str:
        msg = f"Unexpected type for session.python: {type(session.python)}"
        raise TypeError(msg)
    scripts = _scripts_for_python(session.python)
    if not scripts:
        session.skip(f"No example scripts registered for Python {session.python}.")

    deps = _collect_script_dependencies(scripts)
    if deps:
        session.install(*deps)
    session.install(".")

    for script in scripts:
        session.log(f"Running example: {script.relative_to(PROJECT_ROOT)}")
        _ = session.run("python", str(script))


@nox.session(name="run-example", python=False, reuse_venv=False, tags=["examples"])
def run_example(session: nox.Session) -> None:
    """Run a single example script with the matching interpreter.

    Usage:
        nox -s run-example -- path/to/script.py [script args...]
    """

    if not session.posargs:
        session.error("Provide the path to an example script.")

    script_path = Path(session.posargs[0]).resolve()
    if not script_path.exists():
        session.error(f"Example script not found: {script_path}")

    required_python = _infer_python_version_from_path(script_path)
    if required_python is None:
        required_python = _preferred_python_for_script(script_path)

    extra_args = session.posargs[1:]
    tmp_root = Path(session.create_tmp())
    temp_env = tmp_root / f"uv-env-{required_python.replace('.', '_')}"
    temp_env.mkdir(parents=True, exist_ok=True)

    cmd = [
        "uv",
        "run",
        "--project",
        str(PROJECT_ROOT),
        "--python",
        required_python,
        "python",
        str(script_path),
        *extra_args,
    ]
    env = session.env.copy()
    env.update(
        {
            "UV_PROJECT_ENVIRONMENT": str(temp_env),
            "UV_PYTHON_INSTALL_DIR": str(tmp_root / "uv-python"),
        }
    )
    _ = session.run(
        *cmd,
        env=env,
        external=True,
        success_codes=[0],
    )
