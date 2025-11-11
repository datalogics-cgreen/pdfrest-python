import argparse

import nox

nox.options.default_venv_backend = "uv"

python_versions = ["3.10", "3.11", "3.12", "3.13", "3.14"]


@nox.session(name="tests", python=python_versions, reuse_venv=True)
def tests(session: nox.Session) -> None:
    # Define only custom flags
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--no-parallel", action="store_true")
    parser.add_argument(
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

    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group=dev",
        "--reinstall-package=pdfrest",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run(
        "pytest",
        "--cov=pdfrest",
        "--cov-report=term-missing",
        *pytest_args,
    )
