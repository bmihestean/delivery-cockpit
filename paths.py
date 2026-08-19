"""Sibling-repo paths — same assume-siblings-under-~/LevelTwo convention
already used by delivery-status-agent/agent.py and delivery-mcp-server's
DELIVERY_DB_PATH default. No code from any sibling repo is imported here;
only paths to their venv pythons, scripts, and output directories.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent

AI_FUNDAMENTALS = ROOT / "ai-fundamentals-rig"
DELIVERY_COPILOT = ROOT / "delivery-copilot"
DELIVERY_MCP_SERVER = ROOT / "delivery-mcp-server"
DELIVERY_STATUS_AGENT = ROOT / "delivery-status-agent"

REPOS = {
    "ai-fundamentals-rig": AI_FUNDAMENTALS,
    "delivery-copilot": DELIVERY_COPILOT,
    "delivery-mcp-server": DELIVERY_MCP_SERVER,
    "delivery-status-agent": DELIVERY_STATUS_AGENT,
}


def venv_python(repo_dir: Path) -> Path:
    return repo_dir / ".venv" / "bin" / "python"


DATA_RAW = DELIVERY_COPILOT / "data" / "raw"
AGENT_INPUTS = DELIVERY_STATUS_AGENT / "inputs"

RESULTS_DIR = AI_FUNDAMENTALS / "results"
EVAL_RESULTS_DIR = DELIVERY_COPILOT / "eval_results"
REPORTS_DIR = DELIVERY_STATUS_AGENT / "reports"


def list_accounts() -> list[str]:
    if not DATA_RAW.exists():
        return []
    return sorted(p.name for p in DATA_RAW.iterdir() if p.is_dir())
