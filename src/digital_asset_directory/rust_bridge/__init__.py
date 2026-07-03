"""Python orchestration boundary for DAD Rust leaf tools."""

from .dad_scan_core import DadScanCoreResult, run_dad_scan_core

__all__ = ["DadScanCoreResult", "run_dad_scan_core"]
