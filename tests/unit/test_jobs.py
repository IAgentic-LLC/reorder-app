"""Chapter 9, unit tier: pure function, no network, no Postgres, no
queue. `extract_sku` is the one piece of this chapter's logic that
doesn't touch any real service.
"""

from reorder_app.jobs import extract_sku


def test_extracts_a_sku_from_a_typical_question():
    assert extract_sku("Do we need to reorder SKU-3311?") == "SKU-3311"


def test_extracts_a_sku_regardless_of_surrounding_phrasing():
    assert extract_sku("restock SKU-1029?") == "SKU-1029"


def test_returns_none_when_no_sku_is_present():
    assert extract_sku("Do we have enough parts in stock?") is None
