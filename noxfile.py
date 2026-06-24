"""Task orchestration for the Digital Asset Directory hub.

Run `nox -l` to list sessions. Common ones:

    nox -s tests        # full suite (network tests deselected by default)
    nox -s fast         # only fast unit-marked tests
    nox -s changed      # only tests affected by current changes (testmon)
    nox -s lint types validate
"""

from __future__ import annotations

import nox

nox.options.sessions = ["tests", "lint", "types"]
nox.options.reuse_existing_virtualenvs = True


@nox.session
def tests(session: nox.Session) -> None:
    """Full test suite. `network` tests are deselected by default in pyproject."""
    session.install("-e", ".[dev]")
    session.run("pytest", *session.posargs)


@nox.session
def fast(session: nox.Session) -> None:
    """Only fast, pure-logic unit tests."""
    session.install("-e", ".[dev]")
    session.run("pytest", "-m", "unit", *session.posargs)


@nox.session
def changed(session: nox.Session) -> None:
    """Only tests affected by the current working-tree changes (change-driven selection)."""
    session.install("-e", ".[dev]")
    session.run("pytest", "--testmon", *session.posargs)


@nox.session
def lint(session: nox.Session) -> None:
    session.install("ruff>=0.5,<1")
    session.run("ruff", "check", "src", "tests", "scripts")


@nox.session
def types(session: nox.Session) -> None:
    session.install("-e", ".[dev]")
    session.run("mypy", "src/digital_asset_directory")


@nox.session
def validate(session: nox.Session) -> None:
    """Repo contract validation gate."""
    session.install("-e", ".")
    session.run("python", "-m", "digital_asset_directory.cli", "validate", "--hub", ".")
