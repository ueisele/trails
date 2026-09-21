"""The Norwegian height model cut into squares and laid into a mosaic, against a stand-in service."""

import io

import numpy as np
import pytest
import rasterio
from affine import Affine
from trails.io.sources import hoydedata_dtm

LOMSDAL_VISTEN = (12.0, 65.15, 13.75, 65.95)

#: A box small enough to be four squares, so a test can say what every one of them holds.
SMALL = (12.50, 65.50, 12.55, 65.55)


def _tiff(square: hoydedata_dtm.Square, heights: np.ndarray) -> bytes:
    """A GeoTIFF the way the service answers with one."""
    west, _, _, north = square.bounds
    posts_m = (square.bounds[2] - square.bounds[0]) / square.width
    buffer = io.BytesIO()
    with rasterio.open(
        buffer, "w", driver="GTiff", height=square.height, width=square.width, count=1, dtype="float32",
        crs=hoydedata_dtm.CRS, transform=Affine(posts_m, 0.0, west, 0.0, -posts_m, north), nodata=hoydedata_dtm.NODATA,
    ) as out:  # fmt: skip
        out.write(heights.astype(np.float32), 1)
    return buffer.getvalue()


class TestSquaresOver:
    def test_the_box_is_snapped_outwards_to_the_chunk_grid(self):
        squares, transform, across, down = hoydedata_dtm.squares_over(SMALL, posts_m=4.0)
        assert transform.a == 4.0 and transform.e == -4.0
        assert transform.c % hoydedata_dtm.CHUNK_M == 0.0
        assert transform.f % hoydedata_dtm.CHUNK_M == 0.0
        assert across % (hoydedata_dtm.CHUNK_M / 4.0) == 0 and down % (hoydedata_dtm.CHUNK_M / 4.0) == 0
        assert len(squares) == (across * 4.0 / hoydedata_dtm.CHUNK_M) * (down * 4.0 / hoydedata_dtm.CHUNK_M)

    def test_every_square_is_a_whole_number_of_posts(self):
        squares, _, _, _ = hoydedata_dtm.squares_over(SMALL, posts_m=4.0)
        for square in squares:
            assert square.width == square.height == int(hoydedata_dtm.CHUNK_M / 4.0)
            assert square.bounds[2] - square.bounds[0] == pytest.approx(hoydedata_dtm.CHUNK_M)

    def test_the_squares_tile_the_mosaic_exactly(self):
        squares, transform, across, down = hoydedata_dtm.squares_over(SMALL, posts_m=8.0)
        covered = np.zeros((down, across), dtype=int)
        for square in squares:
            row = int(round((transform.f - square.bounds[3]) / 8.0))
            column = int(round((square.bounds[0] - transform.c) / 8.0))
            covered[row : row + square.height, column : column + square.width] += 1
        assert covered.min() == 1 and covered.max() == 1

    def test_a_chunk_that_is_not_a_whole_number_of_posts_is_refused(self):
        with pytest.raises(ValueError, match="whole number"):
            hoydedata_dtm.squares_over(SMALL, posts_m=3.0)

    def test_a_square_past_the_services_own_cap_is_refused(self):
        with pytest.raises(ValueError, match="past the service"):
            hoydedata_dtm.squares_over(SMALL, posts_m=0.5, chunk_m=10_000.0)

    def test_the_lomsdal_visten_box_is_the_ninety_squares_the_build_reads(self):
        squares, transform, across, down = hoydedata_dtm.squares_over(LOMSDAL_VISTEN, posts_m=4.0)
        assert (across, down) == (across, down) and across > 0 and down > 0
        # Ninety kilometres each way at ten to a square, give or take the snap.
        assert 60 <= len(squares) <= 140
        assert transform.a == 4.0


class TestRequestUrl:
    def test_it_asks_for_exactly_the_squares_grid(self):
        square = hoydedata_dtm.Square(bounds=(390000.0, 7260000.0, 400000.0, 7270000.0), width=2500, height=2500)
        url = hoydedata_dtm.request_url(square)
        assert url.startswith(hoydedata_dtm.SERVICE_URL)
        assert "bbox=390000.000%2C7260000.000%2C400000.000%2C7270000.000" in url
        assert "size=2500%2C2500" in url
        assert "bboxSR=25833" in url and "imageSR=25833" in url
        assert "pixelType=F32" in url and "format=tiff" in url


@pytest.fixture
def service():
    """A stand-in for the service: every square comes back at its own corner's height."""
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        parts = dict(piece.split("=", 1) for piece in url.split("?", 1)[1].split("&"))
        west, south, east, north = (float(value) for value in parts["bbox"].replace("%2C", ",").split(","))
        width, height = (int(value) for value in parts["size"].replace("%2C", ",").split(","))
        square = hoydedata_dtm.Square(bounds=(west, south, east, north), width=width, height=height)
        return _tiff(square, np.full((height, width), west / 1000.0, dtype=np.float32))

    fetch.asked = asked  # type: ignore[attr-defined]
    return fetch


class TestMosaic:
    def test_squares_land_where_they_belong(self, service, tmp_path):
        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=service)
        heights, transform = source.mosaic(SMALL, posts_m=8.0)
        squares, expected, across, down = hoydedata_dtm.squares_over(SMALL, posts_m=8.0)
        assert heights.shape == (down, across)
        assert (transform.a, transform.e, transform.c, transform.f) == (expected.a, expected.e, expected.c, expected.f)
        # The west column carries the west square's height and the east column the east one's.
        assert heights[0, 0] == pytest.approx(transform.c / 1000.0)
        assert heights[0, -1] == pytest.approx((transform.c + across * 8.0 - hoydedata_dtm.CHUNK_M) / 1000.0)

    def test_a_second_call_reads_the_cached_mosaic_and_asks_nothing(self, service, tmp_path):
        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=service)
        first, _ = source.mosaic(SMALL, posts_m=8.0)
        asked = len(service.asked)
        again, _ = source.mosaic(SMALL, posts_m=8.0)
        assert len(service.asked) == asked
        assert np.array_equal(first, again)

    def test_a_cached_square_is_not_asked_for_twice(self, service, tmp_path):
        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=service)
        source.mosaic(SMALL, posts_m=8.0)
        asked = len(service.asked)
        # The same squares, a different box: the mosaic is not cached under this
        # name, but every square it needs is.
        source.mosaic((SMALL[0] + 0.001, SMALL[1] + 0.001, SMALL[2] - 0.001, SMALL[3] - 0.001), posts_m=8.0)
        assert len(service.asked) == asked

    def test_what_the_model_leaves_empty_comes_back_as_sea(self, tmp_path):
        def fetch(url: str) -> bytes:
            parts = dict(piece.split("=", 1) for piece in url.split("?", 1)[1].split("&"))
            west, south, east, north = (float(value) for value in parts["bbox"].replace("%2C", ",").split(","))
            width, height = (int(value) for value in parts["size"].replace("%2C", ",").split(","))
            square = hoydedata_dtm.Square(bounds=(west, south, east, north), width=width, height=height)
            heights = np.full((height, width), 120.0, dtype=np.float32)
            heights[: height // 2, :] = hoydedata_dtm.NODATA
            return _tiff(square, heights)

        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=fetch)
        heights, _ = source.mosaic(SMALL, posts_m=8.0)
        assert not (heights == hoydedata_dtm.NODATA).any()
        assert heights.min() == pytest.approx(hoydedata_dtm.SEA_M)
        assert heights.max() == pytest.approx(120.0)

    def test_a_square_that_comes_back_the_wrong_size_is_refused(self, tmp_path):
        def fetch(url: str) -> bytes:
            parts = dict(piece.split("=", 1) for piece in url.split("?", 1)[1].split("&"))
            west, south, east, north = (float(value) for value in parts["bbox"].replace("%2C", ",").split(","))
            square = hoydedata_dtm.Square(bounds=(west, south, east, north), width=7, height=7)
            return _tiff(square, np.zeros((7, 7), dtype=np.float32))

        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=fetch)
        with pytest.raises(RuntimeError, match="came back"):
            source.mosaic(SMALL, posts_m=8.0)

    def test_the_service_is_asked_again_before_the_build_gives_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hoydedata_dtm, "BACKOFF_S", 0.0)
        tries: list[int] = []

        def fetch(url: str) -> bytes:
            tries.append(1)
            if len(tries) < 3:
                raise TimeoutError("nothing came back")
            parts = dict(piece.split("=", 1) for piece in url.split("?", 1)[1].split("&"))
            west, south, east, north = (float(value) for value in parts["bbox"].replace("%2C", ",").split(","))
            width, height = (int(value) for value in parts["size"].replace("%2C", ",").split(","))
            square = hoydedata_dtm.Square(bounds=(west, south, east, north), width=width, height=height)
            return _tiff(square, np.zeros((height, width), dtype=np.float32))

        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=fetch)
        square, _, _, _ = hoydedata_dtm.squares_over(SMALL, posts_m=8.0)
        source.read_square(square[0], posts_m=8.0)
        assert len(tries) == 3

    def test_a_refusal_dressed_as_an_image_is_not_read_as_one(self, tmp_path, monkeypatch):
        """ArcGIS answers `{"error": ...}` with a 200 at its image endpoints.
        Handed to rasterio that raises about a file format, which reads as a
        broken build rather than as the service saying no."""
        monkeypatch.setattr(hoydedata_dtm, "BACKOFF_S", 0.0)

        def fetch(url: str) -> bytes:
            return b'{"error":{"code":400,"message":"Unable to complete operation."}}'

        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=fetch)
        square, _, _, _ = hoydedata_dtm.squares_over(SMALL, posts_m=8.0)
        with pytest.raises(RuntimeError, match="not a TIFF"):
            source.read_square(square[0], posts_m=8.0)
        assert not list((tmp_path / "cache").rglob("*.tif")), "nothing is cached from a refusal"

    def test_a_service_that_never_answers_is_a_named_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hoydedata_dtm, "BACKOFF_S", 0.0)

        def fetch(url: str) -> bytes:
            raise TimeoutError("nothing came back")

        source = hoydedata_dtm.Source(cache_dir=tmp_path / "cache", fetch=fetch)
        square, _, _, _ = hoydedata_dtm.squares_over(SMALL, posts_m=8.0)
        with pytest.raises(RuntimeError, match="did not answer"):
            source.read_square(square[0], posts_m=8.0)


class TestMetadata:
    def test_the_datum_is_stated(self):
        # `atlas` §6.2 requires it of every height source: a model delivered on
        # the ellipsoid would read 36 m high over this ground with nothing to show.
        assert hoydedata_dtm.METADATA.datum == "NN2000"
        assert hoydedata_dtm.METADATA.country == "NO"


class TestHeightsOver:
    def test_cached_squares_are_held_once_without_writing_a_mosaic(self, service, tmp_path, monkeypatch):
        source = hoydedata_dtm.Source(cache_dir=tmp_path, fetch=service)
        heights, transform = source.mosaic(SMALL, posts_m=8.0)
        source._mosaic_file(SMALL, 8.0).unlink()
        before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*.tif")}
        requests = len(service.asked)
        original = source.mosaic
        reads = []

        def mosaic(*args, **kwargs):
            reads.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(source, "mosaic", mosaic)
        read = hoydedata_dtm.heights_over(source, SMALL, posts_m=8.0)
        coordinates = np.array([transform * (1.5, 1.5), transform * (heights.shape[1] - 1.5, 1.5), transform * (-2, -2)])
        expected = [heights[1, 1], heights[1, -2], np.nan]
        np.testing.assert_allclose(read(coordinates), expected, equal_nan=True)
        np.testing.assert_allclose(read(coordinates), expected, equal_nan=True)
        assert len(reads) == 1
        assert len(service.asked) == requests
        assert {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*.tif")} == before

    def test_missing_cached_squares_are_not_downloaded(self, tmp_path):
        def fetch(url):
            pytest.fail("a network build must not fetch a missing square")

        source = hoydedata_dtm.Source(cache_dir=tmp_path, fetch=fetch)
        with pytest.raises(FileNotFoundError, match="height squares are not cached"):
            hoydedata_dtm.heights_over(source, SMALL)
        assert not list(tmp_path.iterdir())
