import pytest
from edgar_names import edgar_region, fund_name_reason, is_fund_filing, name_variants, normalize, parse_location


@pytest.mark.parametrize(
    ("raw", "strict", "brand"),
    [
        ("Modal Labs, Inc.", "modal", "modal labs"),
        ("Modal", "modal", "modal"),
        ("Scale AI, Inc.", "scale", "scale ai"),
        ("Anthropic, PBC", "anthropic", "anthropic"),
        ("The Browser Company of New York Inc.", "browser company of new york", "browser company of new york"),
        ("D'LUX Storage, Inc.", "dlux storage", "dlux storage"),
        ("Character.AI", "character", "character ai"),
        ("Applied Intuition, Inc.", "applied intuition", "applied intuition"),
        ("Hippocratic AI Inc", "hippocratic", "hippocratic ai"),
        ("Acme Technologies Holdings LLC", "acme", "acme technologies"),
        ("Labs", "labs", "labs"),  # never strip to empty
        ("Café Nova Corp.", "cafe nova", "cafe nova"),
        ("AI Fund Management Co", "ai fund management", "ai fund management"),  # middle words stay
    ],
)
def test_normalize(raw, strict, brand):
    n = normalize(raw)
    assert n.strict == strict
    assert n.brand == brand


def test_dba_variants():
    names = {v.strict for v in name_variants("Acme Holdings, Inc. d/b/a Rocket")}
    assert names == {"acme", "rocket"}


@pytest.mark.parametrize(
    "name",
    [
        "Sharp Alpha Opportunity Fund I LLC",
        "021T Capital SPV Ornn, L.P.",
        "Series Fund X, a series of UM Pre-IPO Portfolio Fund II LLC",
        "Kindred Ventures IV, L.P.",
        "Foo Growth III LLC",
        "Bar Partners LLC",
        "Baz Holdings LP",
    ],
)
def test_fund_names(name):
    assert fund_name_reason(name) is not None


@pytest.mark.parametrize("name", ["Modal Labs, Inc.", "Anduril Industries, Inc.", "X Corp", "Acme Holdings, Inc."])
def test_operating_names_pass(name):
    assert fund_name_reason(name) is None


def test_structural_fund_filters():
    assert is_fund_filing("Acme Inc", industry_group="Pooled Investment Fund")
    assert is_fund_filing("Acme Inc", entity_type="Limited Partnership")
    assert is_fund_filing("Acme Inc", exemption_items=["06b", "3C", "3C.1"])
    assert is_fund_filing("Acme Inc", industry_group="Other Technology", entity_type="Corporation") is None


@pytest.mark.parametrize(
    ("text", "region"),
    [
        ("Costa Mesa, California", "CA"),
        ("San Francisco, CA", "CA"),
        ("New York, New York", "NY"),
        ("San Francisco", "CA"),
        ("London, United Kingdom", "united kingdom"),
        ("Remote", None),
        (None, None),
    ],
)
def test_parse_location(text, region):
    assert parse_location(text)[0] == region


def test_edgar_region():
    assert edgar_region("CA") == "CA"
    assert edgar_region("X0") == "united kingdom"
    assert edgar_region("A6") == "canada"
    assert edgar_region(None) is None
