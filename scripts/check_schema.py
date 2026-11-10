"""Validate our collection endpoint against the talent network's own schema.

Pulls the 200-response schema of GET /api/v1/collections/{slug} out of their
OpenAPI document and validates a response with it. --strict also fails on any
key their schema does not define, which is what "a strict subset of their
schema" means in the README.

    python scripts/check_schema.py http://localhost:3000/api/collections/just-raised --strict
    python scripts/check_schema.py response.json --live-spec

With a URL, every page is fetched and checked.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
VENDORED_SPEC = ROOT / "schemas" / "talent-network-openapi.json"
LIVE_SPEC = "https://speedrun-talent-network.com/api/v1/openapi.json?source=just-raised"
PATH = "/api/v1/collections/{slug}"


def _load(src: str) -> dict:
    if src.startswith("http://") or src.startswith("https://"):
        req = urllib.request.Request(src, headers={"User-Agent": "just-raised-schema-check"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    return json.loads(Path(src).read_text())


def response_schema(spec: dict) -> dict:
    schema = spec["paths"][PATH]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    # Inline the components so "#/components/schemas/..." resolves in place.
    return {**schema, "components": spec["components"]}


def allowed_keys(spec: dict) -> tuple[set[str], set[str], set[str]]:
    schema = spec["paths"][PATH]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    top = set(schema["properties"])
    coll = set(spec["components"]["schemas"]["Collection"]["properties"])
    member: set[str] = set()
    for part in schema["properties"]["collection"]["allOf"]:
        props = part.get("properties", {})
        coll |= set(props)
        if "members" in props:
            member = set(props["members"]["items"]["properties"])
    return top, coll, member


def strict_errors(doc: dict, spec: dict) -> list[str]:
    top, coll, member = allowed_keys(spec)
    errs = [f"top-level key not in their schema: {k}" for k in doc if k not in top]
    c = doc.get("collection", {})
    errs += [f"collection key not in their schema: {k}" for k in c if k not in coll]
    for i, m in enumerate(c.get("members", [])):
        errs += [f"members[{i}] key not in their schema: {k}" for k in m if k not in member]
    return errs


def _pages(target: str) -> list[tuple[str, dict]]:
    if not target.startswith("http"):
        return [(target, _load(target))]
    sep = "&" if "?" in target else "?"
    first = _load(f"{target}{sep}page=0")
    out = [(f"{target} page 0", first)]
    for p in range(1, first.get("collection", {}).get("total_pages", 1)):
        out.append((f"{target} page {p}", _load(f"{target}{sep}page={p}")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="URL of our collection endpoint, or a saved JSON response")
    ap.add_argument("--strict", action="store_true", help="also fail on keys their schema does not define")
    ap.add_argument("--live-spec", action="store_true", help="validate against their live OpenAPI, not the vendored copy")
    args = ap.parse_args()

    spec = _load(LIVE_SPEC) if args.live_spec else json.loads(VENDORED_SPEC.read_text())
    validator = Draft202012Validator(response_schema(spec))
    failed = False
    for label, doc in _pages(args.target):
        errs = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in validator.iter_errors(doc)]
        if args.strict:
            errs += strict_errors(doc, spec)
        members = len(doc.get("collection", {}).get("members", []))
        if errs:
            failed = True
            print(f"FAIL {label} ({members} members)")
            for e in errs[:50]:
                print(f"  - {e}")
        else:
            print(f"ok   {label} ({members} members) validates against {spec['info']['title']} v{spec['info']['version']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
