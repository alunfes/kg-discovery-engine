"""Durable file-based hypothesis inventory using JSON storage."""

from __future__ import annotations

import json
import os
from typing import Any

from src.schema.hypothesis_card import HypothesisCard

_PRIVATE_SUBDIR = "private_alpha"
_INVENTORY_FILE = "inventory.json"
_INDEX_FILE = "index.json"


class HypothesisStore:
    """Durable inventory of hypothesis cards stored as JSON.

    Storage structure::

        {store_dir}/
          inventory.json       - list of all non-private HypothesisCards
          private_alpha/       - private_alpha level cards (filesystem-separated)
          index.json           - ID to secrecy_level mapping for fast lookup

    Private-alpha cards are stored in a separate subdirectory to enforce
    secrecy separation at the filesystem level.
    """

    def __init__(self, store_dir: str) -> None:
        """Initialise the store, creating directories if needed."""
        self._store_dir = store_dir
        self._private_dir = os.path.join(store_dir, _PRIVATE_SUBDIR)
        os.makedirs(self._store_dir, exist_ok=True)
        os.makedirs(self._private_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _inventory_path(self) -> str:
        """Return the path to inventory.json."""
        return os.path.join(self._store_dir, _INVENTORY_FILE)

    def _index_path(self) -> str:
        """Return the path to index.json."""
        return os.path.join(self._store_dir, _INDEX_FILE)

    def _private_inventory_path(self) -> str:
        """Return the path to private_alpha/inventory.json."""
        return os.path.join(self._private_dir, _INVENTORY_FILE)

    def _load_json_list(self, path: str) -> list[dict[str, Any]]:
        """Load a JSON list from a file; return [] if missing or corrupt."""
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_json_list(self, path: str, data: list[dict[str, Any]]) -> None:
        """Atomically write a JSON list to a file."""
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)

    def _load_index(self) -> dict[str, str]:
        """Load index.json -> {hypothesis_id: secrecy_level}."""
        if not os.path.exists(self._index_path()):
            return {}
        try:
            with open(self._index_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_index(self, index: dict[str, str]) -> None:
        """Persist index.json."""
        tmp = self._index_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
        os.replace(tmp, self._index_path())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, card: HypothesisCard) -> None:
        """Save a hypothesis card. private_alpha cards go to separate dir."""
        if card.secrecy_level == "private_alpha":
            path = self._private_inventory_path()
        else:
            path = self._inventory_path()

        records = self._load_json_list(path)
        existing_ids = {r["hypothesis_id"] for r in records}
        if card.hypothesis_id not in existing_ids:
            records.append(card.to_dict())
            self._save_json_list(path, records)

        index = self._load_index()
        index[card.hypothesis_id] = card.secrecy_level
        self._save_index(index)

    def load_all(self, include_private: bool = False) -> list[HypothesisCard]:
        """Load all cards. private_alpha excluded unless include_private=True."""
        records = self._load_json_list(self._inventory_path())
        cards = [HypothesisCard.from_dict(r) for r in records]
        if include_private:
            private_records = self._load_json_list(self._private_inventory_path())
            cards.extend(HypothesisCard.from_dict(r) for r in private_records)
        return cards

    def load_by_secrecy(self, secrecy_level: str) -> list[HypothesisCard]:
        """Load cards matching a specific secrecy level."""
        if secrecy_level == "private_alpha":
            records = self._load_json_list(self._private_inventory_path())
        else:
            records = self._load_json_list(self._inventory_path())
        return [
            HypothesisCard.from_dict(r)
            for r in records
            if r.get("secrecy_level") == secrecy_level
        ]

    def load_by_status(self, validation_status: str) -> list[HypothesisCard]:
        """Load cards matching a specific validation status."""
        all_cards = self.load_all(include_private=True)
        return [c for c in all_cards if c.validation_status == validation_status]

    def get_stats(self) -> dict:
        """Return inventory statistics: counts by secrecy level, status, scope."""
        all_cards = self.load_all(include_private=True)
        by_secrecy: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for card in all_cards:
            by_secrecy[card.secrecy_level] = by_secrecy.get(card.secrecy_level, 0) + 1
            by_status[card.validation_status] = by_status.get(card.validation_status, 0) + 1
            by_scope[card.market_scope] = by_scope.get(card.market_scope, 0) + 1
        return {
            "total": len(all_cards),
            "by_secrecy": by_secrecy,
            "by_status": by_status,
            "by_scope": by_scope,
        }

    def save_batch(self, cards: list[HypothesisCard]) -> None:
        """Save a batch of hypothesis cards."""
        for card in cards:
            self.save(card)
