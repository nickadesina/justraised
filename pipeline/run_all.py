"""Run the nightly pipeline end to end: companies, wider portfolio, Form Ds, match, score."""

from __future__ import annotations

import argparse
import logging

from . import config
from .clients import SecClient
from .fetch_companies import fetch_companies
from .fetch_formd import fetch_filings, update_index
from .fetch_portfolio import fetch_portfolio
from .match import run_match
from .score import run_score


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="publish even if High matches dropped sharply")
    ap.add_argument("--no-gate", action="store_true", help="fetch every Form D XML, not just name candidates")
    args = ap.parse_args()

    fetch_companies()
    fetch_portfolio()
    sec = SecClient()
    try:
        index = update_index(sec, config.today())
        fetch_filings(sec, index, config.today(), no_gate=args.no_gate)
    finally:
        sec.close()
    run_match()
    run_score(force=args.force)


if __name__ == "__main__":
    main()
