"""Parse a Form D primary_doc.xml into one flat row.

Paths checked against live filings on 2026-11-09 (schema X0708). Two
differences from the design doc: newOrAmendment is a boolean ``isAmendment``
plus ``previousAccessionNumber``, and dateOfFirstSale is either a ``value``
or a ``yetToOccur`` flag.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from lxml import etree


def _text(node: etree._Element | None, path: str) -> str | None:
    if node is None:
        return None
    found = node.find(path)
    if found is None or found.text is None:
        return None
    value = found.text.strip()
    return value or None


def _amount(value: str | None) -> tuple[float | None, bool]:
    """Return (amount, indefinite)."""
    if value is None:
        return None, False
    if value.strip().lower() == "indefinite":
        return None, True
    try:
        return float(value.replace(",", "")), False
    except ValueError:
        return None, False


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() == "true"


def parse_primary_doc(xml: bytes) -> dict[str, Any]:
    root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=True))
    # Some filings declare a default namespace; strip it so plain paths work.
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag.startswith("{"):
            el.tag = el.tag.split("}", 1)[1]

    issuer = root.find("primaryIssuer")
    offering = root.find("offeringData")
    addr = issuer.find("issuerAddress") if issuer is not None else None
    tof = offering.find("typeOfFiling") if offering is not None else None
    amounts = offering.find("offeringSalesAmounts") if offering is not None else None

    total_offering, offering_indefinite = _amount(_text(amounts, "totalOfferingAmount"))
    total_sold, _ = _amount(_text(amounts, "totalAmountSold"))

    first_sale_raw = _text(tof, "dateOfFirstSale/value")
    try:
        first_sale = date.fromisoformat(first_sale_raw) if first_sale_raw else None
    except ValueError:
        first_sale = None

    persons: list[str] = []
    surnames: list[str] = []
    for p in root.findall("relatedPersonsList/relatedPersonInfo"):
        first = _text(p, "relatedPersonName/firstName") or ""
        last = _text(p, "relatedPersonName/lastName") or ""
        full = " ".join(x for x in (first, last) if x)
        if full:
            persons.append(full)
        if last:
            surnames.append(last)

    prev_names = [
        v.text.strip()
        for v in root.findall("primaryIssuer/issuerPreviousNameList/value")
        if v.text and v.text.strip().lower() != "none"
    ]
    items = [i.text.strip() for i in root.findall("offeringData/federalExemptionsExclusions/item") if i.text]

    return {
        "submission_type": _text(root, "submissionType"),
        "cik": (_text(issuer, "cik") or "").lstrip("0") or None,
        "entity_name": _text(issuer, "entityName"),
        "entity_type": _text(issuer, "entityType") or _text(issuer, "entityTypeOtherDesc"),
        "jurisdiction": _text(issuer, "jurisdictionOfInc"),
        "year_of_inc": _text(issuer, "yearOfInc/value"),
        "city": _text(addr, "city"),
        "state": _text(addr, "stateOrCountry"),
        "previous_names": prev_names,
        "industry_group": _text(offering, "industryGroup/industryGroupType"),
        "exemptions": items,
        "is_amendment": bool(_bool(_text(tof, "newOrAmendment/isAmendment"))),
        "previous_accession": _text(tof, "newOrAmendment/previousAccessionNumber"),
        "date_of_first_sale": first_sale,
        "first_sale_yet_to_occur": bool(_bool(_text(tof, "dateOfFirstSale/yetToOccur"))),
        "total_offering_amount": total_offering,
        "offering_indefinite": offering_indefinite,
        "total_amount_sold": total_sold,
        "related_persons": persons,
        "related_surnames": surnames,
    }
