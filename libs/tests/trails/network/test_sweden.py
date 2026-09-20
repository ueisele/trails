"""The Swedish build's own decisions: which classes go in, what the masks hold, what a key is.

Loading the registers needs the country file and two downloads, so what is
tested here is everything around that, as for Norway: the class tables, the
masks the derived fields are read against, and that the key and the table are
the shared ones under this country's names.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon
from trails.io.sources import naturvardsregistret, topografi50
from trails.network import graphs, sweden
from trails.network.sweden import (
    COST_FACTORS,
    METRIC_CRS,
    MOUNTAIN_WALKED_CLASSES,
    PATH_CLASSES,
    PROTECTED_FORM,
    PROTECTED_ID,
    PROTECTED_NAME,
    RECORDED_SOURCES,
    SOURCE_NAMES,
    TRAIL_CLASSES,
    UNMARKED_CLASSES,
    WINTER_CLASSES,
    Params,
    fingerprint,
    masks_from,
    protected_table,
    zone_around,
)
from trails.routing import NetworkSource


def lines(*offsets: float, classes: tuple[str | None, ...] = ()) -> gpd.GeoDataFrame:
    """One east-west line per offset, each with a Topografi 50 class."""
    stated = classes or (None,) * len(offsets)
    return gpd.GeoDataFrame(
        {topografi50.TYPE: list(stated)},
        geometry=[LineString([(0, offset), (100, offset)]) for offset in offsets],
        crs=METRIC_CRS,
    )


def network(**overrides: gpd.GeoDataFrame) -> list[NetworkSource]:
    """The five sources a mask needs to exist, empty unless given."""
    empty = gpd.GeoDataFrame({topografi50.TYPE: pd.Series(dtype="object")}, geometry=[], crs=METRIC_CRS)
    keys = {"Leder": sweden.LEDER, "T50_trails": sweden.T50_TRAILS, "T50_paths": sweden.T50_PATHS, "T50_roads": sweden.T50_ROADS, "OSM": sweden.OSM}
    return [NetworkSource(name, overrides.get(key, empty)) for key, name in keys.items()]


class TestClasses:
    def test_every_unmarked_class_is_a_path_class(self):
        assert set(UNMARKED_CLASSES) <= set(PATH_CLASSES) | set(MOUNTAIN_WALKED_CLASSES)

    def test_a_trail_class_is_never_a_path_class(self):
        assert not set(TRAIL_CLASSES) & (set(PATH_CLASSES) | set(MOUNTAIN_WALKED_CLASSES))

    def test_a_winter_class_is_never_walked(self):
        assert not set(WINTER_CLASSES) & (set(TRAIL_CLASSES) | set(PATH_CLASSES) | set(MOUNTAIN_WALKED_CLASSES))

    def test_every_source_has_a_cost_but_the_ferries(self):
        assert set(COST_FACTORS) == set(SOURCE_NAMES) - {sweden.FERRIES}

    def test_the_register_is_not_a_record_that_a_path_exists(self):
        assert sweden.LEDER not in RECORDED_SOURCES


class TestMasksFrom:
    def test_every_register_trail_is_in_the_marked_mask(self):
        masks = masks_from(network(Leder=lines(0, 10)))
        assert len(masks.marked) == 2 and len(masks.unmarked) == 0

    def test_every_topografi_trail_joins_them_and_the_worn_path_is_unmarked(self):
        masks = masks_from(network(T50_trails=lines(0, classes=("Vandringsled",)), T50_paths=lines(10, 20, classes=("Gångstig", "Traktorväg"))))
        assert len(masks.marked) == 1 and len(masks.unmarked) == 1

    def test_every_recording_source_is_in_the_recorded_mask(self):
        masks = masks_from(
            network(T50_trails=lines(0), T50_paths=lines(5, classes=("Gångstig",)), T50_roads=lines(10), OSM=lines(20), Leder=lines(30))
        )
        assert len(masks.recorded) == 4

    def test_a_class_that_stopped_being_a_class_is_an_error(self):
        with pytest.raises(ValueError, match="Topografi 50 classifies"):
            masks_from(network(T50_paths=lines(0, classes=("Stig",))))


class TestParams:
    def test_the_shared_fields_are_there_and_nothing_else_is_needed(self):
        params = Params(cache_dir=".cache")
        assert params.approach_km == 15.0 and params.trail_name_m == 25.0
        assert not hasattr(params, "ut_routes")


def protected(*areas: tuple[str, str, str]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            PROTECTED_ID: [identity for identity, _, _ in areas],
            PROTECTED_NAME: [name for _, name, _ in areas],
            PROTECTED_FORM: [form for _, _, form in areas],
        },
        geometry=[Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]) for _ in areas],
        crs=METRIC_CRS,
    )


class TestSharedUnderSwedishNames:
    def test_the_key_is_the_shared_one_under_this_country_s_rules(self):
        sources = network(T50_paths=lines(0, classes=("Gångstig",)))
        masks = masks_from(sources)
        areas = protected(("2001225", "Abisko", "Nationalpark"))
        assert fingerprint(sources, masks, Params(cache_dir=".cache"), areas) == graphs.fingerprint(
            sources, masks, Params(cache_dir=".cache"), areas, sweden.RULES
        )

    def test_the_table_speaks_the_register_s_columns_in_a_sign_s_words(self):
        table = protected_table(protected(("2001225", "Abisko", "Nationalpark")).to_crs("EPSG:4326"))
        assert table[0]["id"] == "2001225" and table[0]["name"] == "Abisko" and table[0]["form"] == "national park"

    def test_the_zone_is_measured_in_sweref(self):
        area = gpd.GeoDataFrame(geometry=[Polygon([(18.5, 68.3), (18.6, 68.3), (18.6, 68.35), (18.5, 68.35)])], crs="EPSG:4326")
        zone = zone_around(area, 10.0)
        assert zone.to_crs(METRIC_CRS).area.sum() > area.to_crs(METRIC_CRS).area.sum()
        assert naturvardsregistret.CRS == METRIC_CRS


class TestHikingRelations:
    def test_membership_names_several_routes_and_keeps_way_names(self):
        ways = gpd.GeoDataFrame(
            {"osm_id": [10, 20, 30], "name": ["Local name", "Other way", None]},
            geometry=[LineString([(0, 0), (1, 0)])] * 3,
            crs=METRIC_CRS,
            index=[3, 5, 7],
        )
        relations = pd.DataFrame(
            [
                {
                    "osm_id": 1,
                    "way_ids": (10,),
                    "name": "Stage A",
                    "ref": "A",
                    "from": "Start",
                    "to": "End",
                    "website": "https://example.org/a",
                    "operator": "Region",
                },
                {"osm_id": 2, "way_ids": (10, 30), "name": "Stage B", "ref": "B", "from": "End", "to": "Next", "website": None, "operator": None},
                {"osm_id": 3, "way_ids": (20,), "name": None, "ref": None, "from": None, "to": None, "website": None, "operator": None},
            ]
        )
        named = sweden.with_hiking_relations(ways, relations)
        assert named["route_name"].tolist() == ["Stage A / Stage B", "Other way", "Stage B"]
        assert named.loc[3, "route_osm_id"] == "1 / 2"
        assert named.loc[3, "route_ref"] == "A / B"
        assert named.loc[3, "route_from"] == "End / Start"
        assert named.loc[3, "route_to"] == "End / Next"
        assert named.loc[3, "route_website"] == "https://example.org/a"
        assert named.loc[3, "name"] == "Local name"
        assert named.loc[5, "route_osm_id"] is None
        assert "route_name" not in ways
        assert named.geometry.equals(ways.geometry)

    def test_no_relations_preserves_names(self):
        ways = gpd.GeoDataFrame({"osm_id": [10], "name": [None]}, geometry=[LineString([(0, 0), (1, 0)])], crs=METRIC_CRS)
        named = sweden.with_hiking_relations(ways, pd.DataFrame())
        assert named["route_name"].isna().all()
        assert named["route_osm_id"].isna().all()


def test_relation_identity_continues_inside_a_stage():
    """A way boundary with different local names is still one hiking stage."""
    from trails.routing.chains import chains_of

    ways = gpd.GeoDataFrame(
        {"osm_id": [10, 20], "name": ["Local path", None]},
        geometry=[LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])],
        crs=METRIC_CRS,
    )
    relations = pd.DataFrame(
        [
            {
                "osm_id": 2343343,
                "way_ids": (10, 20),
                "name": "Bergslagsleden Etapp 1",
                "ref": "1",
                "from": "Kloten",
                "to": "Gillersklack",
                "website": "https://www.bergslagsleden.se/etapper/leden/etapp-1/",
                "operator": None,
            }
        ]
    )
    named = sweden.with_hiking_relations(ways, relations)
    chains = chains_of(NetworkSource(sweden.OSM, named, identity_field="route_name"), metric_crs=METRIC_CRS)
    assert len(chains) == 1
    assert chains.iloc[0]["identity"] == "Bergslagsleden Etapp 1"
    assert chains.iloc[0]["length_m"] == ways.length.sum()
