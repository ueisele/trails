"""Map-specific settings and source selection, without a graph or live service."""

import dataclasses
import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import geopandas as gpd
import pytest
from shapely.geometry import Point, box
from trails.io.sources import naturvardsregistret as nvr
from trails.processing.trees import TREES
from trails.visualization import maps

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "analysis/scripts"))
    return importlib.import_module("lomsdal_visten")


def test_each_map_names_its_gateway_form_and_check(builder):
    assert (builder.PARKS["lomsdal-visten"].gateway, builder.PARKS["lomsdal-visten"].check_route) == ("Mosjøen", "Sjøbergmarsj")
    assert (builder.PARKS["abisko"].gateway, builder.PARKS["abisko"].check_route) == ("Abisko", "BD 21")
    assert builder.PARKS["abisko"].form == nvr.NATIONAL_PARK
    assert builder.PARKS["abisko"].county == ("norrbotten",)
    which = builder.PARKS["malingsbo-kloten"]
    assert which.gateway == "Kopparberg"
    assert which.check_route is None and which.naturkartan is None
    assert which.form == nvr.NATURE_CONSERVATION_AREA
    assert which.kind_label == "nature conservation area"
    assert which.app_name == "Malingsbo-Kloten Atlas"
    assert which.bounds == TREES[which.stem].box


def test_boundary_loader_asks_for_the_form_and_the_union(builder, capsys):
    which = builder.PARKS["malingsbo-kloten"]
    frame = gpd.GeoDataFrame(
        {
            nvr.AREA_ID: ["county-objects"],
            nvr.AREA_NAME: [which.name],
            nvr.AREA_FORM: [which.form],
            "AREA_HA": [0.0],
            "LAN": ["counties"],
            "KOMMUN": ["municipalities"],
        },
        geometry=[box(*which.bounds)],
        crs="EPSG:4326",
    )
    register = Mock()
    register.find_one.return_value = frame
    found = builder.load_swedish_boundary(which, register)
    register.find_one.assert_called_once_with(which.name, form=which.form, exact=True, dissolve=True)
    assert found.geometry.equals(frame.geometry)
    assert "Nature conservation area: Malingsbo-Kloten" in capsys.readouterr().out


def test_county_remains_are_read_once_per_remain_id(builder, monkeypatch):
    which = builder.PARKS["malingsbo-kloten"]
    sources = {}
    for county in which.county:
        source = Mock(version="2026-09-20")
        source.remains.return_value = gpd.GeoDataFrame(
            {"remain_id": ["shared", county], "kind": ["farmstead site", "summer farm"]},
            geometry=[Point(15.2, 60.0), Point(15.3, 60.0)],
            crs="EPSG:4326",
        )
        sources[county] = source
    factory = Mock(side_effect=lambda county, cache_dir: sources[county])
    monkeypatch.setattr(builder.kulturmiljoregistret, "Source", factory)
    found, version = builder.load_swedish_remains(which, which.bounds, "unused")
    assert found["remain_id"].tolist() == ["shared", *which.county]
    assert found.crs.to_epsg() == 4326
    assert [call.args[0] for call in factory.call_args_list] == list(which.county)
    for source in sources.values():
        source.remains.assert_called_once_with(which.bounds, force_download=False)
    assert version == "; ".join(f"{county}: 2026-09-20" for county in which.county)
    single = dataclasses.replace(which, county=(which.county[0],))
    assert builder.load_swedish_remains(single, single.bounds, "unused")[1] == "2026-09-20"
    empty, version = builder.load_swedish_remains(dataclasses.replace(which, county=()), which.bounds, "unused")
    assert empty.empty and version is None


def test_an_unconfigured_route_check_is_reported_as_skipped(builder, capsys):
    report = importlib.import_module("route_graph")
    report.report_check_route(gpd.GeoDataFrame(), builder.PARKS["malingsbo-kloten"].check_route)
    assert "Route elevation check skipped" in capsys.readouterr().out
    assert "gateway" not in report.Country._fields and "check_route" not in report.Country._fields


def test_swedish_graph_uses_the_maps_form_and_gateway(builder, monkeypatch):
    report = importlib.import_module("route_graph")
    which = builder.PARKS["malingsbo-kloten"]
    register = Mock()
    register.find_one.return_value = gpd.GeoDataFrame({nvr.AREA_NAME: [which.name]}, geometry=[box(*which.bounds)], crs="EPSG:4326")
    monkeypatch.setattr(report.naturvardsregistret, "Source", Mock(return_value=register))
    monkeypatch.setattr(report.sweden.Params, "from_args", Mock(return_value=report.sweden.Params(cache_dir="unused")))
    loaded = Mock(sources=[], protected=gpd.GeoDataFrame(), versions={report.sweden.LEDER: None, report.sweden.T50_PATHS: None})
    monkeypatch.setattr(report.sweden, "load_sources", Mock(return_value=loaded))
    monkeypatch.setattr(report.sweden, "masks_from", Mock(return_value=[]))
    monkeypatch.setattr(report.sweden, "build", Mock(return_value=(Mock(), Mock())))
    landmarks = Mock()
    monkeypatch.setattr(report, "load_swedish_landmarks", landmarks)
    report.graph_sweden(which, Mock(), report.COUNTRIES[which.country])
    register.find_one.assert_called_once_with(which.name, form=which.form, exact=True, dissolve=True)
    assert landmarks.call_args.args[2] == "Kopparberg"


@pytest.mark.parametrize("park", ["abisko", "malingsbo-kloten"])
def test_swedish_tile_defaults_follow_the_selected_tree(builder, monkeypatch, park):
    script = importlib.import_module("lantmateriet_tiles")
    source = Mock()
    source.reader = Mock(spec=script.lantmateriet.FtpFile, modified="20260920000000")
    monkeypatch.setattr(script.lantmateriet, "Source", Mock(return_value=source))
    version = Mock(return_value=(1, True))
    monkeypatch.setattr(script.lantmateriet, "version_for", version)
    assert script.main(["--park", park, "--max-zoom", "8"]) == 0
    tree = TREES[park]
    root = ROOT / "analysis/output/tiles" / tree.provider / "topowebb"
    assert version.call_args.args[0] == root
    source.copy_tiles.assert_called_once_with(tree.box, range(8, 9), root / "1")


def test_a_swedish_tree_version_does_not_move_the_other_map(monkeypatch):
    key = "lantmateriet-malingsbo-kloten"
    base = maps.BaseMap.LANTMATERIET_TOPO_MALINGSBO_KLOTEN
    abisko = maps.PROVIDERS["lantmateriet"]
    abisko_layer = maps._BASE_LAYERS[maps.BaseMap.LANTMATERIET_TOPO].copy()
    monkeypatch.setattr(maps, "PROVIDERS", maps.PROVIDERS.copy())
    monkeypatch.setattr(maps, "_BASE_LAYERS", {name: row.copy() for name, row in maps._BASE_LAYERS.items()})
    version = 2
    changed = maps.tile_tree_version(key, version)
    assert changed.tiles == f"/tiles/{key}/topowebb/{version}/"
    assert maps.provider_of(base) is changed
    assert maps._BASE_LAYERS[base]["tiles"] == changed.tiles + "{z}/{x}/{y}.png"
    assert maps.PROVIDERS["lantmateriet"] == abisko
    assert maps._BASE_LAYERS[maps.BaseMap.LANTMATERIET_TOPO] == abisko_layer
    for attr, layer in (
        ("heights", "dem"),
        ("shade", "shade"),
        ("slope", "slope"),
        ("vegetation", "vegetation"),
        ("forest", "forest"),
        ("mire", "mire"),
    ):
        assert getattr(changed, attr).tiles == TREES["malingsbo-kloten"].prefix(layer)


def test_new_page_settings_and_companions_name_its_own_provider(builder):
    which = builder.PARKS["malingsbo-kloten"]
    page = maps.create_map(bounds=which.bounds, base=which.base, title=which.app_name, companions=which.companions)
    html = page.get_root().render()
    assert maps.provider_of_map(page).key == "lantmateriet-malingsbo-kloten"
    assert "/tiles/lantmateriet-malingsbo-kloten/topowebb/1/" in html
    assert "malingsbo-kloten.webmanifest" in html
    assert "Malingsbo-Kloten Atlas" in html


@pytest.mark.parametrize("target", ["drive-all", "drive-both"])
def test_drive_all_filters_scenes_runs_together_and_sums_statuses(tmp_path, target):
    # Isolate the logs too: a unit test must not replace a real browser report.
    (tmp_path / "Makefile").write_text((ROOT / "Makefile").read_text().replace("/tmp/drive-", f"{tmp_path}/drive-"))
    pages = tmp_path / "analysis/output"
    pages.mkdir(parents=True)
    for stem in ("first", "second", "no-scene"):
        (pages / f"{stem}.html").touch()
    executable = tmp_path / "uv"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import pathlib, sys, time\n"
        "if '-c' in sys.argv:\n"
        "    print('first second unbuilt')\n"
        "    raise SystemExit(0)\n"
        "stem = pathlib.Path(sys.argv[sys.argv.index('--page') + 1]).stem\n"
        "pathlib.Path(stem + '.started').touch()\n"
        "for attempt in range(100):\n"
        "    if all(pathlib.Path(s + '.started').exists() for s in ('first', 'second')):\n"
        "        print(stem + ' driven together')\n"
        "        raise SystemExit({'first': 1, 'second': 2}[stem])\n"
        "    time.sleep(0.01)\n"
        "raise SystemExit(10)\n"
    )
    executable.chmod(0o755)
    result = subprocess.run(
        ["bash", "-c", f"command make {target} MISE="],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert "first driven together" in result.stdout and "second driven together" in result.stdout
    assert "Error 3" in result.stderr
    assert result.returncode != 0
    assert not (tmp_path / "no-scene.started").exists()
    assert not (tmp_path / "unbuilt.started").exists()
