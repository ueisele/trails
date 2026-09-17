"""Tests for the Trafiklab GTFS source."""

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from trails.io.sources import trafiklab

#: A box around Abisko, in GeoPandas order.
BOX = (18.15, 68.139, 19.1, 68.46)

STOPS = """stop_id,stop_name,stop_lat,stop_lon
740000114,Abisko turiststation,68.358164,18.780111
740023825,Abisko Östra E10,68.350874,18.831071
740078899,Stordalen E10,68.30,18.60
740099999,Registered but unserved,68.20,18.30
740000001,Stockholm Centralstation,59.330,18.058
"""

# Stordalen's trip touches it and nothing else; the unserved stop is in no trip.
STOP_TIMES = """trip_id,stop_id,stop_sequence
t_rail,740000114,1
t_rail,740023825,2
t_bus,740000114,1
t_bus,740078899,2
t_taxi,740000114,1
t_far,740000001,1
"""

TRIPS = """trip_id,route_id
t_rail,r_98
t_bus,r_91
t_taxi,r_957
t_far,r_98
"""

ROUTES = """route_id,route_short_name,route_long_name,route_type,agency_id
r_98,98,Stockholm-Narvik,102,sj
r_91,91,Kiruna-Riksgränsen,3,ltn
r_957,957,Anropsstyrd,1501,ltn
"""

AGENCY = """agency_id,agency_name
sj,SJ
ltn,Länstrafiken Norrbotten
"""


#: The register's answer: the station is 234 m from where the feed put it, the
#: bus stop is where the feed put it, and Stordalen is not in here at all. The
#: suffixed place repeats the station and must be skipped rather than counted
#: twice.
REGISTER = """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex">
 <dataObjects>
  <StopPlace id="SE:050:StopPlace:59149">
   <keyList><KeyValue><Key>rikshallplats</Key><Value>740000114</Value></KeyValue></keyList>
   <Name>Abisko oestra</Name>
   <Centroid><Location><Longitude>18.782000</Longitude><Latitude>68.356100</Latitude></Location></Centroid>
  </StopPlace>
  <StopPlace id="SE:050:StopPlace:59149_2">
   <keyList><KeyValue><Key>rikshallplats</Key><Value>740000114</Value></KeyValue></keyList>
   <Name>Abisko oestra</Name>
   <Centroid><Location><Longitude>99.000000</Longitude><Latitude>9.000000</Latitude></Location></Centroid>
  </StopPlace>
  <StopPlace id="SE:050:StopPlace:58480">
   <keyList><KeyValue><Key>rikshallplats</Key><Value>740023825</Value></KeyValue></keyList>
   <Name>Abisko Oestra E10</Name>
   <Centroid><Location><Longitude>18.831071</Longitude><Latitude>68.350874</Latitude></Location></Centroid>
  </StopPlace>
 </dataObjects>
</PublicationDelivery>
"""


def _feed(tmp_path: Path, routes: str = ROUTES, register: str | None = REGISTER) -> Path:
    """Write a small GTFS archive and the register beside it, and return the feed."""
    archive = tmp_path / "gtfs" / "sweden.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("stops.txt", STOPS)
        out.writestr("stop_times.txt", STOP_TIMES)
        out.writestr("trips.txt", TRIPS)
        out.writestr("routes.txt", routes)
        out.writestr("agency.txt", AGENCY)
    if register is not None:
        with zipfile.ZipFile(tmp_path / "gtfs" / "stops-netex.zip", "w") as out:
            out.writestr(trafiklab.REGISTER_MEMBER, register)
    return archive


class TestStops:
    """Tests for Source.stops."""

    def test_keeps_the_box_and_only_what_a_line_calls_at(self, tmp_path):
        """Stockholm is outside the box; the unserved stop is inside it and in no
        trip. Registered is not served, the same rule Norway's loader applies."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX)

        assert sorted(gdf["stop_id"]) == ["740000114", "740023825", "740078899"]
        assert gdf.crs.to_epsg() == 4326

    def test_a_line_is_filed_under_its_mode_and_labelled_with_its_word(self, tmp_path):
        """**The word matters as much as the mode.** A shared taxi is drawn as a
        bus stop, because that is where it calls, and must not read as a bus that
        turns up by itself."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")

        assert gdf.loc["Abisko turiststation", "rail_lines"] == "98 long-distance train"
        assert gdf.loc["Abisko turiststation", "bus_lines"] == "91 bus / 957 shared taxi"
        assert gdf.loc["Abisko turiststation", "operator"] == "Länstrafiken Norrbotten / SJ"
        assert gdf.loc["Abisko turiststation", "modes"] == "train / bus"
        assert pd.isna(gdf.loc["Stordalen E10", "rail_lines"])

    def test_the_line_order_is_the_same_every_build(self, tmp_path):
        """**The lines arrive in a set and a set has no order.** Left as they
        came, the same feed wrote the list one way and then the other, because
        Python salts string hashes per process -- so a popup read differently
        each time it was built. Numbered lines go in numeric order."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")
        assert gdf.loc["Abisko turiststation", "bus_lines"].split(" / ") == ["91 bus", "957 shared taxi"]
        assert trafiklab.line_order("91 bus") < trafiklab.line_order("950 express bus") < trafiklab.line_order("60098 express bus")
        assert trafiklab.line_order("60098 express bus") < trafiklab.line_order("F7 Nordlandsbanen")

    def test_the_stop_id_is_the_national_one(self, tmp_path):
        """It is what a Resrobot board is asked for, so the map needs no table of
        its own to link one."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX)
        assert "740000114" in set(gdf["stop_id"])

    def test_a_route_type_nobody_mapped_is_said_and_left_out(self, tmp_path, capsys):
        """Silently dropping it would leave the stop reading as one nothing calls
        at, which is a different claim."""
        _feed(tmp_path, routes=ROUTES.replace("1501,ltn", "9999,ltn"))
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")

        assert gdf.loc["Abisko turiststation", "bus_lines"] == "91 bus"
        assert "9999" in capsys.readouterr().out

    def test_is_cached_and_the_key_names_the_modes(self, tmp_path):
        _feed(tmp_path)
        source = trafiklab.Source(cache_dir=str(tmp_path))
        source.stops(BOX)
        source.stops(BOX)
        assert any("rail-air-water-bus" in path.name for path in tmp_path.rglob("trafiklab_stops_*"))

    def test_a_box_nothing_calls_in_is_empty_rather_than_broken(self, tmp_path):
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops((0.0, 0.0, 1.0, 1.0))
        assert len(gdf) == 0
        assert list(gdf.columns) == trafiklab.COLUMNS


class TestPlacedByTheRegister:
    """Tests for the positions the national stop register supplies."""

    def test_a_station_moves_to_where_the_register_says_it_is(self, tmp_path, capsys):
        """**GTFS Sverige 2 puts a station where its bus stop is.** Measured over
        the Abisko box: five of six stations up to 249 m out, the bus stops right
        to the metre."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")
        moved = gdf.loc["Abisko turiststation"].geometry

        assert (round(moved.y, 6), round(moved.x, 6)) == (68.3561, 18.782)
        assert "Abisko turiststation" in capsys.readouterr().out

    def test_a_suffixed_place_does_not_win(self, tmp_path):
        """The register splits a place by type -- 59149 beside 59149_2 -- and all
        of them carry the same centroid, so only the unsuffixed one is read. The
        fixture gives the suffixed one an absurd position to prove it is not."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")
        assert gdf.loc["Abisko turiststation"].geometry.y > 60

    def test_a_stop_the_register_does_not_know_stays_where_the_feed_had_it(self, tmp_path, capsys):
        """Left where it was and **said**, rather than dropped or guessed at."""
        _feed(tmp_path)
        gdf = trafiklab.Source(cache_dir=str(tmp_path)).stops(BOX).set_index("name")
        stordalen = gdf.loc["Stordalen E10"].geometry

        assert (round(stordalen.y, 4), round(stordalen.x, 4)) == (68.30, 18.60)
        assert "Stordalen E10" in capsys.readouterr().out

    def test_without_the_register_key_the_build_stops(self, tmp_path):
        """**Not a fallback to the feed's own positions.** Those are the ones
        that drew a station 249 m from where it is, and a build that quietly used
        them would look exactly like a build that had the register."""
        _feed(tmp_path, register=None)
        source = trafiklab.Source(cache_dir=str(tmp_path))
        with patch.dict("os.environ", {trafiklab.REGISTER_KEY_VARIABLE: ""}, clear=False):
            with pytest.raises(trafiklab.TrafiklabError, match=trafiklab.REGISTER_KEY_VARIABLE):
                source.stops(BOX)


class TestDataset:
    """Tests for Source.dataset."""

    def test_the_feed_is_kept_rather_than_fetched_again(self, tmp_path):
        """A Bronze key allows fifty calls a month and the file is 44 MB; a build
        that re-downloaded would spend the quota on what it already has."""
        _feed(tmp_path)
        with patch("requests.get") as get:
            trafiklab.Source(cache_dir=str(tmp_path)).dataset()
        get.assert_not_called()

    def test_without_a_key_it_says_which_variable_and_which_file(self, tmp_path):
        source = trafiklab.Source(cache_dir=str(tmp_path))
        with patch.dict("os.environ", {trafiklab.KEY_VARIABLE: ""}, clear=False):
            with pytest.raises(trafiklab.TrafiklabError, match=trafiklab.KEY_VARIABLE):
                source.dataset()

    def test_the_key_is_not_in_the_failure(self, tmp_path):
        """It is substituted into the URL at the last moment, and the URL is not
        reported: a traceback in a log must not carry the credential."""
        source = trafiklab.Source(cache_dir=str(tmp_path), api_key="s3cret")
        with patch("requests.get", side_effect=__import__("requests").ConnectionError("boom")):
            with pytest.raises(trafiklab.TrafiklabError) as raised:
                source.dataset()
        assert "s3cret" not in str(raised.value)

    def test_it_streams_the_download_to_disk(self, tmp_path):
        """44 MB does not go through memory to get to a file."""
        source = trafiklab.Source(cache_dir=str(tmp_path), api_key="k")
        payload = io.BytesIO(b"zipbytes")
        with patch("requests.get") as get:
            get.return_value.__class__.iter_content = lambda self, chunk_size: iter([payload.getvalue()])
            get.return_value.raise_for_status.return_value = None
            path = source.dataset()
        assert get.call_args.kwargs["stream"] is True
        assert path.read_bytes() == b"zipbytes"
