from digital_asset_directory.extractors import classify_asset, extract_bytes


def test_secret_redaction_and_semantic_extraction():
    text = "# Evaluation Harness\napi_key=super-secret-value\nA knowledge graph learning loop needs human review."
    extracted = extract_bytes("docs/evaluation.md", text.encode(), 5000, True)
    assert "super-secret-value" not in extracted["excerpt"]
    assert extracted["redaction_count"] == 1
    assert "evaluation" in extracted["tags"]
    assert "build_knowledge_graph" in extracted["capabilities"]


def test_asset_classification():
    assert classify_asset("schemas/asset.schema.json") == "schema"
    assert classify_asset("tests/test_something.py") == "test"
    assert classify_asset("src/app.py") == "code"
