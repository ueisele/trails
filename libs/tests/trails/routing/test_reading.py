"""Tests for reading back what a chain carries.

A chain spans several source features and joins the values they disagree on, so
everything downstream that translates or counts one of those values has to see
the parts rather than the string. These are the three helpers that do.
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString
from trails.routing.chains import chains_of, parts_of, translate_joined, whole_way_length
from trails.routing.sources import NetworkSource

CRS = "EPSG:25833"

LABELS = {"dig": "Digitised from a map", "fot": "Photogrammetry", "P": "Private road", "K": "Municipal road"}


def chains(*items: tuple[str, str | None, float]) -> gpd.GeoDataFrame:
    """Build a chain frame from what the helpers actually read.

    Args:
        *items: ``(source, identity, length_m)`` per chain

    Returns:
        The chains, with a placeholder geometry
    """
    return gpd.GeoDataFrame(
        {
            "source": [source for source, _, _ in items],
            "identity": [identity for _, identity, _ in items],
            "length_m": [length for _, _, length in items],
        },
        geometry=[LineString([(0, index), (1, index)]) for index in range(len(items))],
        crs=CRS,
    )


class TestPartsOf:
    """Test parts_of."""

    def test_one_value_reads_as_one_part(self):
        """Test the ordinary case: the features agreed."""
        assert parts_of("sti") == ["sti"]

    def test_a_combined_value_reads_as_its_parts(self):
        """Test what the helper exists for: a run that changes character."""
        assert parts_of("sti / traktorveg") == ["sti", "traktorveg"]

    def test_nothing_reads_as_no_parts(self):
        """Test that a chain saying nothing yields nothing to translate."""
        assert parts_of(None) == []

    def test_the_way_a_nullable_column_says_nothing_reads_as_no_parts(self):
        """Test the value that gets through every other check.

        ``pd.NA`` is neither None nor a float nan, and ``str()`` turns it into
        the literal text ``<NA>`` — which would then be looked up, missed, and
        shown to a reader as a value.
        """
        assert parts_of(pd.NA) == []

    def test_an_empty_string_reads_as_no_parts(self):
        """Test the other way these registers write nothing."""
        assert parts_of("  ") == []


class TestTranslateJoined:
    """Test translate_joined."""

    def test_a_code_becomes_its_label(self):
        """Test the ordinary case."""
        assert translate_joined(pd.Series(["dig"]), LABELS).tolist() == ["Digitised from a map"]

    def test_both_codes_of_a_combined_value_become_labels(self):
        """Test the case translating the whole string would get wrong.

        Looked up whole, ``dig / fot`` matches nothing and comes back as the
        raw codes, which is a popup asserting a path with no way to judge it.
        """
        assert translate_joined(pd.Series(["dig / fot"]), LABELS).tolist() == ["Digitised from a map / Photogrammetry"]

    def test_a_code_the_table_does_not_cover_passes_through(self):
        """Test that an untranslated value still says something."""
        assert translate_joined(pd.Series(["xyz"]), LABELS).tolist() == ["xyz"]

    def test_two_codes_meaning_one_thing_are_not_repeated(self):
        """Test that a label is not written twice where two codes share it."""
        assert translate_joined(pd.Series(["dig / dig"]), {"dig": "Digitised"}).tolist() == ["Digitised"]

    def test_nothing_stays_nothing(self):
        """Test that a chain with nothing to say gains no text."""
        assert translate_joined(pd.Series([None]), LABELS).tolist() == [None]


class TestCombining:
    """Test that joining a chain's values is idempotent.

    ``_combine`` is exercised through :func:`chains_of` rather than directly,
    because what matters is what lands on a chain.
    """

    def test_a_value_that_is_already_a_join_is_not_joined_again(self):
        """Test the case a source value being a list of its own creates.

        A Turrutebasen segment looked after by two clubs arrives as one string
        naming both. A chain over two such segments used to read every club
        once per segment, so a popup said *Helgeland friluftsråd / Mosåsens
        venner / Helgeland friluftsråd / Mosåsens venner*.
        """
        run = NetworkSource(
            "T",
            gpd.GeoDataFrame(
                {"club": ["Mosåsens venner / Helgeland friluftsråd", "Helgeland friluftsråd / Mosåsens venner"]},
                geometry=[LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])],
                crs=CRS,
            ),
            attributes=("club",),
        )
        assert chains_of(run)["club"].tolist() == ["Helgeland friluftsråd / Mosåsens venner"]

    def test_pieces_that_disagree_still_carry_both(self):
        """Test that the splitting did not turn a join into a choice."""
        run = NetworkSource(
            "T",
            gpd.GeoDataFrame(
                {"typeveg": ["sti", "traktorveg"]},
                geometry=[LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])],
                crs=CRS,
            ),
            attributes=("typeveg",),
        )
        assert chains_of(run)["typeveg"].tolist() == ["sti / traktorveg"]


class TestWholeWayLength:
    """Test whole_way_length."""

    def test_a_way_that_never_divides_is_the_whole_of_itself(self):
        """Test that the common case reports the chain's own length exactly."""
        assert whole_way_length(chains(("N50 roads", "1234", 3200.0))).tolist() == [3200.0]

    def test_the_arms_of_a_branching_road_add_up_to_the_road(self):
        """Test the figure the popup covers the lost highlight with.

        Clicking Tveråvegen used to light all 15.6 km; now it lights the arm
        under the cursor, and only both numbers together are true.
        """
        road = chains(("N50 roads", "1234", 3200.0), ("N50 roads", "1234", 12400.0))
        assert whole_way_length(road).tolist() == [15600.0, 15600.0]

    def test_a_chain_with_no_identity_has_no_wider_way(self):
        """Test that an unnamed line reports nothing rather than itself.

        FKB carries no names at all, so this is most of the network.
        """
        assert np.isnan(whole_way_length(chains(("FKB", None, 400.0))).iloc[0])

    def test_two_sources_naming_a_way_alike_have_not_agreed(self):
        """Test that identities are counted within a source, never across.

        Chains are built per source and never compete over geometry; a name
        shared by two datasets is a coincidence, not one way.
        """
        both = chains(("OSM", "Fjelltrimmen", 400.0), ("Turrutebasen", "Fjelltrimmen", 3000.0))
        assert whole_way_length(both).tolist() == [400.0, 3000.0]

    def test_a_chain_across_two_registered_ways_counts_each_of_them(self):
        """Test the case the register creates by calling one run two roads."""
        spanning = chains(("N50 roads", "1234 / 5678", 100.0), ("N50 roads", "1234", 900.0), ("N50 roads", "5678", 2000.0))
        assert whole_way_length(spanning).iloc[0] == pytest.approx(3000.0)

    def test_the_whole_is_never_less_than_the_stretch(self):
        """Test the property the union reading was chosen for.

        A popup reading "this stretch 3.2 km, the road in total 1.1" would be
        worse than showing neither.
        """
        spanning = chains(("N50 roads", "1234 / 5678", 5000.0), ("N50 roads", "1234", 100.0))
        whole = whole_way_length(spanning)
        assert (whole >= spanning["length_m"]).all()

    def test_no_chains_at_all_is_not_an_error(self):
        """Test the empty frame."""
        assert whole_way_length(chains()).empty

    def test_a_placeholder_name_is_not_a_way(self):
        """Test the trap the ``ignore`` list exists for.

        A register writing *Ukjent* has said it does not know the name, not
        that these two stretches are one route. Counted as a name, a 16 m stub
        reports the total of every other stretch the register also had no name
        for — which is the ``pd.NA``-as-identity trap in the register's own
        words.
        """
        unknown = chains(("Turrutebasen", "Ukjent", 17.0), ("Turrutebasen", "Ukjent", 12_900.0))
        assert whole_way_length(unknown, ignore={"Ukjent"}).isna().all()

    def test_a_real_name_beside_a_placeholder_still_counts(self):
        """Test that ignoring one identity does not discard the others."""
        mixed = chains(("Turrutebasen", "Ukjent / Sjøbergmarsjruta", 400.0), ("Turrutebasen", "Sjøbergmarsjruta", 20_000.0))
        assert whole_way_length(mixed, ignore={"Ukjent"}).iloc[0] == pytest.approx(20_400.0)

    def test_nothing_is_ignored_unless_the_caller_says_so(self):
        """Test that which values name nothing is the register's business.

        This module has no opinion about Norwegian; the default has to be that
        every identity counts.
        """
        unknown = chains(("Turrutebasen", "Ukjent", 17.0), ("Turrutebasen", "Ukjent", 12_900.0))
        assert whole_way_length(unknown).iloc[0] == pytest.approx(12_917.0)
