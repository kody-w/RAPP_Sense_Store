"""Pytest fixtures for sense validator tests."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

FIXTURES = Path(__file__).parent / "fixtures"
