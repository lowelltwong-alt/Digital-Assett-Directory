from __future__ import annotations

from digital_asset_directory.mcp_conformance import run_synthetic_conformance
from digital_asset_directory.mcp_server import DADGraphMCPServer

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_local_server_passes_synthetic_remote_conformance_without_remote_connection():
    server = DADGraphMCPServer(ROOT)
    report = run_synthetic_conformance(server.handle_request)
    assert report["status"] == "passed", report
    assert report["synthetic_only"] is True
    assert report["remote_connected"] is False
    assert report["execution_authorized"] is False
