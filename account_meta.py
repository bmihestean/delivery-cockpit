"""Per-account branding metadata (display name, accent color, logo,
description) for the cockpit UI only.

Kept separate from delivery-copilot/accounts.py (the canonical account/index
logic) for the same reason paths.py duplicates private_data_root() rather than
importing it: the two repos run in separate venvs, so cross-repo imports
aren't practical, and private-account metadata must never live inside a
public git repo. Stored in ~/.delivery-program/accounts.json, a sibling of
the existing config.json.

The filesystem (paths.list_accounts()) remains the sole source of truth for
which accounts exist; this module only decorates known slugs with optional
metadata, and returns sane defaults for any slug with no config entry.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import paths

ACCOUNTS_CONFIG_PATH = Path.home() / ".delivery-program" / "accounts.json"
LOGOS_DIR = Path.home() / ".delivery-program" / "logos"
DEFAULT_ACCENT = "#9CA3AF"
DEFAULT_ENTITLEMENTS = {"visible_to": ["*"], "manageable_by": ["*"]}


@dataclass
class AccountMeta:
    slug: str
    display_name: str
    accent_color: str
    logo: str | None
    description: str
    entitlements: dict = field(default_factory=lambda: dict(DEFAULT_ENTITLEMENTS))


def load_accounts_config() -> dict:
    if ACCOUNTS_CONFIG_PATH.exists():
        try:
            return json.loads(ACCOUNTS_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_account_meta(slug: str, updates: dict) -> None:
    config = load_accounts_config()
    config.setdefault(slug, {})
    config[slug].update(updates)
    ACCOUNTS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_CONFIG_PATH.write_text(json.dumps(config, indent=2))


def get_account_meta(slug: str) -> AccountMeta:
    entry = load_accounts_config().get(slug, {})
    return AccountMeta(
        slug=slug,
        display_name=entry.get("display_name") or slug.replace("-", " ").replace("_", " ").title(),
        accent_color=entry.get("accent_color") or DEFAULT_ACCENT,
        logo=entry.get("logo"),
        description=entry.get("description", ""),
        entitlements=entry.get("entitlements") or dict(DEFAULT_ENTITLEMENTS),
    )


def list_accounts_meta() -> list[AccountMeta]:
    return [get_account_meta(slug) for slug in paths.list_accounts()]
