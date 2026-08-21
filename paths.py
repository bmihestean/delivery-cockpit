"""Sibling-repo paths — same assume-siblings-under-~/Projects/delivery-leader-program
convention already used by delivery-status-agent/agent.py and
delivery-mcp-server's DELIVERY_DB_PATH default. No code from any sibling
repo is imported here; only paths to their venv pythons, scripts, and
output directories.

Private-root logic is duplicated from delivery-copilot/accounts.py rather
than imported — same reasoning as the PRICING constant duplicated across
four other repos. This is the one place in the cockpit that both *reads*
and *writes* ~/.delivery-program/config.json (the Private notes tab is
where the path actually gets configured).
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".delivery-program" / "config.json"
DEFAULT_PRIVATE_ROOT = Path.home() / "Projects" / "delivery-leader-program-private"


def private_data_root() -> Path:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text())
            configured = cfg.get("private_data_root")
            if configured:
                return Path(configured).expanduser()
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_PRIVATE_ROOT


def save_private_data_root(path: Path) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"private_data_root": str(path)}, indent=2))

ROOT = Path(__file__).parent.parent

AI_FUNDAMENTALS = ROOT / "ai-fundamentals-rig"
DELIVERY_COPILOT = ROOT / "delivery-copilot"
DELIVERY_MCP_SERVER = ROOT / "delivery-mcp-server"
DELIVERY_STATUS_AGENT = ROOT / "delivery-status-agent"
DELIVERY_EVALS = ROOT / "delivery-evals"

REPOS = {
    "ai-fundamentals-rig": AI_FUNDAMENTALS,
    "delivery-copilot": DELIVERY_COPILOT,
    "delivery-mcp-server": DELIVERY_MCP_SERVER,
    "delivery-status-agent": DELIVERY_STATUS_AGENT,
    "delivery-evals": DELIVERY_EVALS,
}


def venv_python(repo_dir: Path) -> Path:
    return repo_dir / ".venv" / "bin" / "python"


DATA_RAW = DELIVERY_COPILOT / "data" / "raw"
AGENT_INPUTS = DELIVERY_STATUS_AGENT / "inputs"

RESULTS_DIR = AI_FUNDAMENTALS / "results"
EVAL_RESULTS_DIR = DELIVERY_COPILOT / "eval_results"
REPORTS_DIR = DELIVERY_STATUS_AGENT / "reports"
EVALS_RESULTS_DIR = DELIVERY_EVALS / "results"


def private_data_dir() -> Path:
    return private_data_root() / "data" / "raw"


def private_agent_inputs_dir() -> Path:
    return private_data_root() / "agent_inputs"


def list_accounts() -> list[str]:
    public = {p.name for p in DATA_RAW.iterdir() if p.is_dir()} if DATA_RAW.exists() else set()
    priv_dir = private_data_dir()
    private = {p.name for p in priv_dir.iterdir() if p.is_dir()} if priv_dir.exists() else set()
    return sorted(public | private)


def list_agent_inputs() -> dict[str, Path]:
    """Display label -> full path, merging public demo inputs and private
    ones. Private files are prefixed so they're never mistaken for the
    synthetic demo data in a dropdown."""
    result: dict[str, Path] = {}
    if AGENT_INPUTS.exists():
        for f in sorted(AGENT_INPUTS.glob("*.md")):
            result[f.name] = f
    priv_dir = private_agent_inputs_dir()
    if priv_dir.exists():
        for f in sorted(priv_dir.glob("*.md")):
            result[f"🔒 {f.name}"] = f
    return result
