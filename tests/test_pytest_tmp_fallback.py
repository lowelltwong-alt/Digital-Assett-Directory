from __future__ import annotations

import re

from conftest import _bounded_fallback_tmp_name, _pytest_standard_tmp_name


def test_standard_tmp_name_mirrors_pytest_sanitization_and_length() -> None:
    node_name = "test:param/[value] with a name that exceeds pytest's normal limit"

    result = _pytest_standard_tmp_name(node_name)

    assert result == re.sub(r"[\W]", "_", node_name)[:30]
    assert len(result) <= 30


def test_bounded_fallback_name_is_unique_stable_prefixed_and_private() -> None:
    node_id = "tests/test_example.py::test_case[very-long-human-readable-parameter]"

    first = _bounded_fallback_tmp_name(node_id)
    second = _bounded_fallback_tmp_name(node_id)

    assert len(first) == 23
    assert first != second
    assert first.rsplit("-", 1)[0] == second.rsplit("-", 1)[0]
    assert "very-long-human-readable-parameter" not in first
    assert re.fullmatch(r"t-[0-9a-f]{12}-[0-9a-f]{8}", first)
