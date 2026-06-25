import json

from digital_asset_directory.extractors import classify_asset, extract_bytes, infer_semantics
from digital_asset_directory.utils import redact_sensitive_text

import pytest

pytestmark = pytest.mark.unit


def test_secret_redaction_and_semantic_extraction():
    text = "# Evaluation Harness\napi_key=super-secret-value\nA knowledge graph learning loop needs human review."
    extracted = extract_bytes("docs/evaluation.md", text.encode(), 5000, True)
    assert "super-secret-value" not in extracted["excerpt"]
    assert extracted["redaction_count"] == 1
    assert "evaluation" in extracted["tags"]
    assert "build_knowledge_graph" in extracted["capabilities"]
    assert "evaluation_harness" in extracted["asset_patterns"]
    assert extracted["pattern_evidence"]["evaluation_harness"]


def test_redaction_covers_json_and_env_secret_forms():
    json_red, json_count = redact_sensitive_text('{"api_key": "AKIA_SECRET_VALUE_1234"}')
    env_red, env_count = redact_sensitive_text("API_KEY=AKIA_SECRET_VALUE_1234")
    assert "AKIA_SECRET_VALUE_1234" not in json_red
    assert "AKIA_SECRET_VALUE_1234" not in env_red
    assert json_count >= 1 and env_count >= 1


def test_extract_bytes_redacts_secrets_from_all_derived_fields():
    data = (
        "# Service config\n"
        "api_key: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345\n"
        '{"client_secret": "sk-ABCDEFGHIJKLMNOPQRSTUV0123"}\n'
    ).encode()
    extracted = extract_bytes("config/service.yaml", data, 5000, True)
    # No secret value may survive in ANY derived field: title, description, excerpt, or tokens.
    blob = json.dumps(extracted).lower()
    assert "ghp_abcdefghijklmnopqrstuvwxyz012345" not in blob
    assert "sk-abcdefghijklmnopqrstuv0123" not in blob
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345" not in extracted["chunk_text"]
    assert extracted["redaction_count"] >= 2


def test_keyword_matching_uses_word_boundaries():
    # Substring false positives must not fire: "management"->agent, "paragraph"->graph, "storage"->rag.
    benign = infer_semantics("docs/notes.md", "The management paragraph documents storage of records.")
    assert "agent" not in benign["tags"]
    assert "build_knowledge_graph" not in benign["capabilities"]
    assert "retrieve_context" not in benign["capabilities"]
    # Real phrases at word boundaries still match.
    real = infer_semantics("docs/eval.md", "This is an evaluation harness for a knowledge graph.")
    assert "evaluation" in real["tags"]
    assert "build_knowledge_graph" in real["capabilities"]


def test_asset_classification():
    assert classify_asset("schemas/asset.schema.json") == "schema"
    assert classify_asset("tests/test_something.py") == "test"
    assert classify_asset("src/app.py") == "code"
    assert classify_asset("workflows/agent_pipeline.md") == "workflow"
