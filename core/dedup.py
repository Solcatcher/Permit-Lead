"""Deduplication across runs.

Per the spec: dedupe using jurisdiction + permit number + address + relevant
dates. We persist a lightweight "seen keys" index (one line per key) in
CSV form at <data_dir>/dedup_index.csv so dedup works across days, not just
within a single run's in-memory list. This avoids needing a database while
still being safe to run daily indefinitely (the index only grows by the
number of genuinely new records each day).

If storage.backends includes "sqlite", the SQLite table's UNIQUE constraint
on the same key columns provides a second, authoritative line of defense
(see core/storage.py) — the CSV index here is what keeps CSV-only setups
correctly deduplicated too.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterable, List, Set, Tuple

from core.schema import PermitRecord

logger = logging.getLogger(__name__)

DedupKey = Tuple[str, str, str, str, str]


class DedupIndex:
    def __init__(self, index_path: Path):
        self.index_path = index_path
        self._seen: Set[DedupKey] = set()
        self._load()

    def _load(self) -> None:
        if not self.index_path.exists():
            return
        with open(self.index_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # header
            for row in reader:
                if len(row) == 5:
                    self._seen.add(tuple(row))  # type: ignore[arg-type]
        logger.info("Loaded %d known permit keys from dedup index", len(self._seen))

    def _append(self, keys: Iterable[DedupKey]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.index_path.exists()
        with open(self.index_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(
                    ["jurisdiction", "permit_number", "address", "application_date", "issue_date"]
                )
            for key in keys:
                writer.writerow(list(key))

    def filter_new(self, records: List[PermitRecord]) -> List[PermitRecord]:
        """Return only records whose dedup key hasn't been seen before,
        and record those new keys as seen (persisted immediately so a crash
        mid-run doesn't cause duplicate re-processing on retry).
        """
        new_records: List[PermitRecord] = []
        new_keys: List[DedupKey] = []
        seen_this_batch: Set[DedupKey] = set()

        for record in records:
            key = record.dedup_key()
            if key in self._seen or key in seen_this_batch:
                continue
            seen_this_batch.add(key)
            new_keys.append(key)
            new_records.append(record)

        if new_keys:
            self._append(new_keys)
            self._seen.update(new_keys)

        logger.info(
            "Dedup: %d records in, %d new, %d already-seen",
            len(records),
            len(new_records),
            len(records) - len(new_records),
        )
        return new_records
