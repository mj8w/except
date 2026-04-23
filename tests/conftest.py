from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root used by the test suite."""

    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def sample_module_path(project_root: Path) -> Path:
    """Return the shared sample module used by analyzer and CLI tests."""

    return project_root / "tests" / "fixtures" / "sample_module.py"


@pytest.fixture(scope="session")
def implicit_exception_module_path(project_root: Path) -> Path:
    """Return the module used to specify implicit exception inference behavior."""

    return project_root / "tests" / "fixtures" / "implicit_exception_module.py"


@pytest.fixture(scope="session")
def caught_exception_module_path(project_root: Path) -> Path:
    """Return the module used to specify caught-exception suppression behavior."""

    return project_root / "tests" / "fixtures" / "caught_exception_module.py"


@pytest.fixture(scope="session")
def requests_module_path(project_root: Path) -> Path:
    """Return the module used to exercise imported third-party calls."""

    return project_root / "tests" / "fixtures" / "requests_module.py"


@pytest.fixture(scope="class")
def sample_module_test_context(
    request: pytest.FixtureRequest, project_root: Path, sample_module_path: Path
) -> None:
    """Attach shared sample module paths to pytest test classes."""

    request.cls.project_root = project_root
    request.cls.sample_module_path = sample_module_path
