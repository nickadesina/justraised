"""Human-reviewed match decisions, pinned so they never need re-review.

File format (YAML)::

    confirm:                       # these pairs are a match, at High confidence
      - cik: "0001234567"
        slug: modal
        note: "checked founders on the Form D, 2026-11-10"
    reject:                        # never match this issuer to this company
      - cik: "0007654321"
        slug: modal
        note: "Modal Health Partners, unrelated"
    block_cik:                     # never match this issuer to anything
      - cik: "0001111111"
        note: "SPV"

A confirm entry wins over the automatic ladder; a reject entry removes the
pair even if the ladder scores it High.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class _OverrideLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = super().construct_mapping(node, deep=deep)
        if len(mapping) != len(node.value):
            raise ValueError(f"duplicate YAML key in overrides near line {node.start_mark.line + 1}")
        return mapping


def _cik(value: object) -> str:
    return str(value).strip().lstrip("0") or "0"


@dataclass
class Overrides:
    confirm: dict[str, str] = field(default_factory=dict)  # cik -> slug
    reject: set[tuple[str, str]] = field(default_factory=set)  # (cik, slug)
    block_cik: set[str] = field(default_factory=set)
    spv_ignore: set[str] = field(default_factory=set)
    spv_reject: set[tuple[str, str]] = field(default_factory=set)  # (vehicle CIK, target slug)

    def confirmed_slug(self, cik: str) -> str | None:
        return self.confirm.get(_cik(cik))

    def is_rejected(self, cik: str, slug: str) -> bool:
        c = _cik(cik)
        return c in self.block_cik or (c, slug) in self.reject

    def is_spv_rejected(self, vehicle_cik: str, target_slug: str) -> bool:
        return target_slug in self.spv_ignore or (_cik(vehicle_cik), target_slug) in self.spv_reject


def load_overrides(path: str | Path, *, slug_aliases: dict[str, str] | None = None) -> Overrides:
    p = Path(path)
    if not p.exists():
        return Overrides()
    raw = yaml.load(p.read_text(), Loader=_OverrideLoader) or {}
    ov = Overrides()
    aliases = slug_aliases or {}

    def canonical(value: object) -> str:
        slug = str(value)
        return aliases.get(slug, slug)

    for row in raw.get("confirm") or []:
        ov.confirm[_cik(row["cik"])] = canonical(row["slug"])
    for row in raw.get("reject") or []:
        ov.reject.add((_cik(row["cik"]), canonical(row["slug"])))
    for row in raw.get("block_cik") or []:
        ov.block_cik.add(_cik(row["cik"]))
    ov.spv_ignore = {canonical(slug) for slug in raw.get("spv_ignore") or []}
    for row in raw.get("spv_reject") or []:
        ov.spv_reject.add((_cik(row["cik"]), canonical(row["slug"])))
    return ov
