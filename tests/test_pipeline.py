import math
from datetime import date
from pathlib import Path

from pipeline.formd_xml import parse_primary_doc
from pipeline.match import HIGH, LOW, MEDIUM, _prep_companies, ladder
from pipeline.score import build_offerings, score

FIXTURES = Path(__file__).parent / "fixtures"


def _companies():
    return _prep_companies(
        [
            {"slug": "modal", "name": "Modal", "tier": "a16z", "location": "New York, New York", "blurb": "Serverless GPUs."},
            {"slug": "acme-robotics", "name": "Acme Robotics", "tier": "speedrun", "location": "San Francisco, CA",
             "blurb": "Founded by Jane Okafor to build warehouse robots."},
            {"slug": "gamma", "name": "Gamma", "tier": "a16z", "location": "San Francisco, California", "blurb": ""},
        ]
    )


def _filing(name, state=None, surnames=()):
    return {"entity_name": name, "state": state, "related_surnames": list(surnames)}


def test_rung1_exact_is_high():
    best = ladder(_filing("Modal Labs, Inc.", "NY"), _companies())[0]
    assert (best.slug, best.rung, best.confidence) == ("modal", "1", HIGH)


def test_rung1_location_conflict_demotes():
    best = ladder(_filing("Gamma, Inc.", "TX"), _companies())[0]
    assert (best.slug, best.rung, best.confidence) == ("gamma", "1", MEDIUM)
    assert "location conflict" in best.notes[0]


def test_subset_names_go_to_review_not_high():
    # token_set_ratio("modal health group", "modal") is 100 and the state matches,
    # but the extra words fail the guard, so a person decides.
    best = [c for c in ladder(_filing("Modal Health Group Inc", "NY"), _companies()) if c.slug == "modal"][0]
    assert (best.rung, best.confidence) == ("3", MEDIUM)
    assert "subset guard" in best.notes[0]
    # Same shape in another state: not even worth a review.
    far = [c for c in ladder(_filing("Modal Health Group Inc", "TX"), _companies()) if c.slug == "modal"][0]
    assert far.confidence == LOW


def test_slug_variant_makes_legal_name_exact():
    comps = _prep_companies([{"slug": "anduril-industries", "name": "Anduril", "tier": "a16z",
                              "location": "Costa Mesa, California", "blurb": ""}])
    best = ladder(_filing("Anduril Industries, Inc.", "CA"), comps)[0]
    assert (best.rung, best.confidence) == ("1", HIGH)


def test_rung3_near_identical_name_needs_location():
    hit = ladder(_filing("AcmeRobotics Inc", "CA"), _companies())[0]
    assert (hit.slug, hit.rung, hit.confidence) == ("acme-robotics", "3", HIGH)
    miss = ladder(_filing("AcmeRobotics Inc", "TX"), _companies())[0]
    assert miss.confidence == LOW


def test_rung4_surname_in_blurb_is_medium():
    cands = ladder(_filing("Acme Robotics Systems Group Inc", "CA", ["Okafor"]), _companies())
    best = [c for c in cands if c.slug == "acme-robotics"][0]
    # token_set 100, guard fails -> Medium via rung 3's review path, surname noted.
    assert best.confidence == MEDIUM and best.surname_hit == "Okafor"


def test_ambiguous_issuer_is_demoted():
    comps = _prep_companies([
        {"slug": "arena", "name": "Arena", "tier": "a16z", "location": None, "blurb": ""},
        {"slug": "arena-2", "name": "Arena", "tier": "speedrun", "location": None, "blurb": ""},
    ])
    cands = ladder(_filing("Arena, Inc.", "CA"), comps)
    assert all(c.confidence == MEDIUM for c in cands)


def test_score_formula():
    assert math.isclose(score(1_000_000, 0, 0), 6.0, rel_tol=1e-6)
    assert math.isclose(score(1_000_000, 1, 45), 1.5, rel_tol=1e-6)
    assert score(None, 3, 10) == 0.0


def _f(adsh, file_date, first_sale, amend=False, prev=None, sold=0.0, offered=None):
    return {
        "adsh": adsh, "cik": "1", "entity_name": "Acme", "city": None, "state": "CA", "industry_group": None,
        "file_date": file_date, "is_amendment": amend, "previous_accession": prev,
        "date_of_first_sale": first_sale, "total_amount_sold": sold, "total_offering_amount": offered,
        "offering_indefinite": False,
    }


def test_amendment_updates_amount_not_window():
    original = _f("a1", date(2026, 9, 1), date(2026, 8, 25), sold=1e6, offered=5e6)
    amendment = _f("a2", date(2026, 11, 1), date(2026, 8, 25), amend=True, prev="a1", sold=4e6, offered=5e6)
    (off,) = build_offerings([original, amendment])
    assert off["first_sale"] == date(2026, 8, 25)
    assert off["amount"] == 4e6 and off["amount_kind"] == "sold"
    assert off["amendments"] == 1


def test_orphan_amendment_uses_its_first_sale_not_file_date():
    amendment = _f("a2", date(2026, 11, 1), date(2026, 5, 1), amend=True, prev="missing", sold=4e6)
    (off,) = build_offerings([amendment])
    assert off["first_sale"] == date(2026, 5, 1)


def test_offering_amount_when_nothing_sold():
    (off,) = build_offerings([_f("a1", date(2026, 11, 1), date(2026, 10, 30), sold=0.0, offered=2e6)])
    assert (off["amount"], off["amount_kind"]) == (2e6, "offering")


def test_parse_primary_doc():
    rec = parse_primary_doc((FIXTURES / "primary_doc.xml").read_bytes())
    assert rec["entity_name"] == "D'LUX Storage, Inc."
    assert rec["cik"] == "2164423"
    assert rec["state"] == "CA" and rec["city"] == "SAN JOSE"
    assert rec["entity_type"] == "Corporation"
    assert rec["industry_group"] == "Other"
    assert rec["is_amendment"] is False
    assert rec["date_of_first_sale"] == date(2026, 10, 26)
    assert rec["total_offering_amount"] == 5000002 and rec["total_amount_sold"] == 249993
    assert "Slinker" in rec["related_surnames"]


# --- wider portfolio and the a16z-person rung --------------------------------

from pipeline.fetch_portfolio import build_universe
from pipeline.match import person_key

PEOPLE = frozenset({person_key("Erin Price-Wright"), person_key("Ben Horowitz")})


def test_person_key_normalizes_form_d_names():
    assert person_key("Schuyler (Baker) Tilney") == "schuyler tilney"
    assert person_key("Erin Price-Wright") == person_key("ERIN PRICE WRIGHT".replace(" WRIGHT", "-WRIGHT"))
    assert person_key("Cher") == ""


def _off(name, slug):
    return {"slug": slug, "name": name, "tier": "a16z", "location": None, "blurb": "", "on_network": False}


def test_off_network_exact_name_needs_corroboration():
    comps = _prep_companies([_off("Relay", "a16z:relay")])
    best = ladder({"entity_name": "Relay, Inc.", "state": "NY", "related_persons": ["Pat Smith"]}, comps, PEOPLE)[0]
    assert best.confidence == MEDIUM and "off-network" in best.notes[0]


def test_a16z_person_promotes_off_network_match():
    comps = _prep_companies([_off("Databricks", "a16z:databricks")])
    f = {"entity_name": "Databricks, Inc.", "state": "CA", "related_persons": ["Ali Ghodsi", "Ben Horowitz"]}
    best = ladder(f, comps, PEOPLE)[0]
    assert (best.confidence, best.a16z_person) == (HIGH, "Ben Horowitz")


def test_a16z_person_promotes_location_conflict():
    comps = _prep_companies([{"slug": "mariana-minerals", "name": "Mariana Minerals", "tier": "a16z",
                              "location": "Moab, Utah", "blurb": ""}])
    f = {"entity_name": "Mariana Minerals Co.", "state": "CA", "related_persons": ["Erin Price-Wright"]}
    assert ladder(f, comps, PEOPLE)[0].confidence == HIGH
    f["related_persons"] = ["Someone Else"]
    assert ladder(f, comps, PEOPLE)[0].confidence == MEDIUM


def test_a16z_person_does_not_rescue_low():
    comps = _prep_companies([{"slug": "modal", "name": "Modal", "tier": "a16z", "location": "New York, NY", "blurb": ""}])
    f = {"entity_name": "Modal Health Group Inc", "state": "TX", "related_persons": ["Ben Horowitz"]}
    assert [c for c in ladder(f, comps, PEOPLE) if c.slug == "modal"][0].confidence == LOW


def test_universe_folds_duplicates_into_network_entry():
    network = [{"slug": "harvey", "name": "Harvey", "tier": "a16z"}]
    extra = [_off("Harvey", "a16z:harvey") | {"website": "https://harvey.ai"}, _off("Databricks", "a16z:databricks")]
    uni = build_universe(network, extra)
    assert [c["slug"] for c in uni] == ["harvey", "a16z:databricks"]
    assert uni[0]["on_network"] is True and uni[0]["website"] == "https://harvey.ai"


# --- investor SPVs ------------------------------------------------------------

import re as _re

from pipeline.spv import brand_phrases, spv_target

_UNI = [
    {"slug": "cursor", "name": "Cursor", "aliases": ["Anysphere"]},
    {"slug": "shield-ai", "name": "Shield AI"},
    {"slug": "saronic-technologies", "name": "Saronic"},
    {"slug": "a16z:koru", "name": "Koru"},
    {"slug": "titan", "name": "Titan"},
    {"slug": "a16z:digital-asset-holdings", "name": "Digital Asset Holdings"},
]


def _target(name, items=None, ignore=()):
    phrases = brand_phrases(_UNI, set(ignore))
    patterns = {p: _re.compile(r"\b" + _re.escape(p) + r"\b") for p in phrases}
    return spv_target(name, items, phrases, patterns)


def test_spv_alias_and_brand_suffix():
    assert _target("HII Anysphere-01, a Series of HII Anysphere LLC") == "cursor"
    assert _target("Greenbird Intelligence Fund, LLC, Series W - Shield AI") == "shield-ai"
    assert _target("HII Saronic-01, a Series of HII Saronic, LLC") == "saronic-technologies"


def test_spv_rejects_common_words_and_managers():
    assert _target("Titan Opportunity Fund II, LP") is None          # common word
    assert _target("51Quid Digital Asset Fund, LP") is None          # every word common
    assert _target("AA Atomics II a Series of Koru Ventures LLC") is None  # manager name


def test_spv_needs_a_vehicle_and_respects_ignore():
    assert _target("Saronic Technologies, Inc.") is None  # an operating company, not a vehicle
    assert _target("HII Saronic-01, a Series of HII Saronic, LLC", ignore={"saronic-technologies"}) is None
