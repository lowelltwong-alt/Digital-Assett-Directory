from __future__ import annotations

import os
import re
import sys
from pathlib import Path
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def _pytest_standard_tmp_name(node_name: str) -> str:
    return re.sub(r"[\W]", "_", node_name)[:30] or "test"


def _bounded_fallback_tmp_name(node_id: str) -> str:
    stable_key = uuid.uuid5(uuid.NAMESPACE_URL, node_id).hex[:12]
    return f"t-{stable_key}-{uuid.uuid4().hex[:8]}"



@pytest.fixture(autouse=True)
def _restore_dad_data_root():
    """Restore DAD_DATA_ROOT after every test.

    A test that leaks an override redirects resolve_data_root() for the rest
    of the pytest process: later tests that validate the live repo fall back
    to stale legacy paths and fail order-dependently.
    """
    before = os.environ.get("DAD_DATA_ROOT")
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("DAD_DATA_ROOT", None)
        else:
            os.environ["DAD_DATA_ROOT"] = before


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Use an ordinary directory when pytest's ACL-managed temp root is denied.

    The opt-in path is useful in restricted Windows tokens where pytest's
    numbered-directory chmod/cleanup can make its own base directory
    unreadable.  Normal runs retain pytest's standard fixture behavior.
    """

    configured_root = os.environ.get("DAD_PYTEST_TMP_ROOT", "").strip()
    if not configured_root:
        return tmp_path_factory.mktemp(_pytest_standard_tmp_name(request.node.name))
    root = Path(configured_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / _bounded_fallback_tmp_name(request.node.nodeid)
    path.mkdir()
    return path
