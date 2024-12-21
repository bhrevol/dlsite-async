"""Nox sessions."""
import os
import shutil
import sys
from pathlib import Path

import nox
from nox import Session, session


os.environ.update({"PDM_IGNORE_SAVED_PYTHON": "1"})

package = "dlsite_async"
python_versions = ["3.13", "3.12", "3.11", "3.10"]
nox.needs_version = ">= 2021.6.6"
nox.options.sessions = (
    "pre-commit",
    "safety",
    "mypy",
    "tests",
    "typeguard",
    "xdoctest",
    "docs-build",
)


@session(name="pre-commit", python=python_versions[0])
def precommit(session: Session) -> None:
    """Lint using pre-commit."""
    session.run_always("pdm", "install", "-G", "lint", external=True)
    args = session.posargs or [
        "run",
        "--all-files",
        "--show-diff-on-failure",
    ]
    session.run("pre-commit", *args)


@session(python=python_versions[0])
def safety(session: Session) -> None:
    """Scan dependencies for insecure packages."""
    session.run_always("pdm", "install", "-G", "safety", external=True)
    session.run("pdm", "export", "-o", "requirements.txt", "--without-hashes")
    session.run("safety", "check", "--full-report", "--file=requirements.txt")


@session(python=python_versions[0])
def mypy(session: Session) -> None:
    """Type-check using mypy."""
    session.run_always(
        "pdm", "install", "-G", "pil", "-G", "mypy", "-G", "tests", external=True
    )
    args = session.posargs or ["src", "tests", "docs/conf.py"]
    session.run("mypy", *args)
    if not session.posargs:
        session.run("mypy", f"--python-executable={sys.executable}", "noxfile.py")


@session(python=python_versions)
def tests(session: Session) -> None:
    """Run the test suite."""
    session.run_always(
        "pdm",
        "install",
        "-G",
        "pil",
        "-G",
        "tests",
        "-G",
        "coverage",
        external=True,
    )
    try:
        session.run("coverage", "run", "--parallel", "-m", "pytest", *session.posargs)
    finally:
        if session.interactive:
            session.notify("coverage", posargs=[])


@session(python=python_versions[0])
def coverage(session: Session) -> None:
    """Produce the coverage report."""
    session.run_always("pdm", "install", "-G", "coverage", external=True)
    args = session.posargs or ["report"]

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")

    session.run("coverage", *args)


@session(python=python_versions[0])
def typeguard(session: Session) -> None:
    """Runtime type checking using Typeguard."""
    session.run_always(
        "pdm",
        "install",
        "-G",
        "pil",
        "-G",
        "typeguard",
        "-G",
        "tests",
        external=True,
    )
    session.run("pytest", f"--typeguard-packages={package}", *session.posargs)


@session(python=python_versions)
def xdoctest(session: Session) -> None:
    """Run examples with xdoctest."""
    session.run_always("pdm", "install", "-G", "pil", "-G", "xdoctest", external=True)
    if session.posargs:
        args = [package, *session.posargs]
    else:
        args = [f"--modname={package}", "--command=all"]
        if "FORCE_COLOR" in os.environ:
            args.append("--colored=1")

    session.run("python", "-m", "xdoctest", *args)


@session(name="docs-build", python=python_versions[0])
def docs_build(session: Session) -> None:
    """Build the documentation."""
    session.run_always("pdm", "install", "-G", "pil", "-G", "docs", external=True)
    args = session.posargs or ["docs", "docs/_build"]
    if not session.posargs and "FORCE_COLOR" in os.environ:
        args.insert(0, "--color")

    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    session.run("sphinx-build", *args)


@session(python=python_versions[0])
def docs(session: Session) -> None:
    """Build and serve the documentation with live reloading on file changes."""
    session.run_always("pdm", "install", "-G", "pil", "-G", "docs", external=True)
    args = session.posargs or ["--open-browser", "docs", "docs/_build"]

    build_dir = Path("docs", "_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)

    session.run("sphinx-autobuild", *args)
