from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from hypothesis import given, strategies as st


def canonical_query(params: list[tuple[str, str]]) -> str:
    """Return a stable query string for cache keys and dedupe records."""
    return urlencode(sorted(params), doseq=True)


@given(st.dictionaries(st.text(min_size=1), st.text(), max_size=8))
def test_canonical_query_round_trips(params: dict[str, str]) -> None:
    encoded = canonical_query(list(params.items()))
    decoded = dict(parse_qsl(encoded, keep_blank_values=True))
    assert decoded == params
    assert canonical_query(list(reversed(params.items()))) == encoded
