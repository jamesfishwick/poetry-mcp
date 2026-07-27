"""Tests for VenueCatalog filtering."""

from poetry_mcp.catalog.venue_catalog import VenueCatalog
from poetry_mcp.models.venue import Venue


def test_filter_venues_tolerates_boolean_payment(tmp_path):
    """A venue with a boolean payment (YAML `payment: yes` -> True) must not crash filtering."""
    catalog = VenueCatalog(venues_dir=tmp_path)
    catalog.index.add(Venue(name="Boolish", payment=True))
    catalog.index.add(Venue(name="Paid", payment="$50/poem"))

    # payment_filter substring-matches only string payments; the bool is skipped,
    # not crashed on (previously raised AttributeError: 'bool' has no 'lower').
    results = catalog.filter_venues(payment_filter="$50")

    assert [v.name for v in results] == ["Paid"]
