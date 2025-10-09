import nox

nox.options.default_venv_backend = "uv"

python_versions = ["3.10", "3.11", "3.12", "3.13", "3.14"]


@nox.session(name="tests", python=python_versions, reuse_venv=True)
def tests(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group=dev",
        "--reinstall-package=pdfrest",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    session.run("pytest", "--cov=pdfrest", "--cov-report=term-missing")
