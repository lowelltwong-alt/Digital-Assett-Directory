import pytest

from digital_asset_directory.ids import asset_id, revision_id

pytestmark = pytest.mark.unit


def test_asset_identity_is_stable_and_revision_is_content_specific():
    first = asset_id("source", "Repo/README.md")
    second = asset_id("source", "repo/readme.md")
    assert first == second
    assert revision_id(first, "abc") == revision_id(first, "abc")
    assert revision_id(first, "abc") != revision_id(first, "def")
