"""Tests for the shared Geonorge per-municipality order client."""

import json
from unittest.mock import Mock, patch

import pytest
import requests
from trails.io.cache import Download as DownloadCache
from trails.io.sources.geonorge_order import KommuneOrderClient


def _mock_response(payload: dict) -> Mock:
    """Build a mock requests response returning the given payload."""
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def order_response() -> dict:
    """A Geonorge order response covering two municipalities."""
    return {
        "files": [
            {"name": "Basisdata_1824_Vefsn_25833_N50Kartdata_FGDB.zip", "downloadUrl": "https://example.test/vefsn"},
            {"name": "Basisdata_1813_Bronnoy_25833_N50Kartdata_FGDB.zip", "downloadUrl": "https://example.test/bronnoy"},
        ],
    }


@pytest.fixture
def client(tmp_path) -> KommuneOrderClient:
    """A client writing into a temporary download cache."""
    return KommuneOrderClient("some-uuid", "demo", DownloadCache(str(tmp_path)))


class TestOrder:
    """Tests for placing an order."""

    def test_sends_uuid_areas_and_format(self, client, order_response):
        with patch("requests.post", return_value=_mock_response(order_response)) as mock_post:
            client.order(["1824", "1813"])

        line = mock_post.call_args.kwargs["json"]["orderLines"][0]
        assert line["metadataUuid"] == "some-uuid"
        assert [area["code"] for area in line["areas"]] == ["1824", "1813"]
        assert line["formats"] == [{"name": "FGDB"}]

    def test_returns_name_and_url_per_file(self, client, order_response):
        with patch("requests.post", return_value=_mock_response(order_response)):
            files = client.order(["1824"])

        assert files[0].name.startswith("Basisdata_1824")
        assert files[0].url == "https://example.test/vefsn"

    def test_entries_without_a_url_are_dropped(self, client):
        payload = {"files": [{"name": "x.zip"}, {"name": "Basisdata_1824_y.zip", "downloadUrl": "https://example.test/y"}]}

        with patch("requests.post", return_value=_mock_response(payload)):
            assert len(client.order(["1824"])) == 1

    def test_empty_file_list_raises(self, client):
        with patch("requests.post", return_value=_mock_response({"files": []})), pytest.raises(ValueError, match="no downloadable files"):
            client.order(["1824"])

    def test_http_error_propagates(self, client):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("503")

        with patch("requests.post", return_value=response), pytest.raises(requests.HTTPError):
            client.order(["1824"])


class TestFetch:
    """Tests for the caching behaviour around downloads."""

    def test_prefix_determines_the_cached_filename(self, client):
        assert client.local_name("1824") == "demo_1824.zip"

    def test_downloads_each_missing_municipality(self, client, order_response):
        with (
            patch("requests.post", return_value=_mock_response(order_response)),
            patch.object(client.downloads, "download") as mock_download,
        ):
            paths = client.fetch(["1824", "1813"])

        assert mock_download.call_count == 2
        assert set(paths) == {"1824", "1813"}

    def test_skips_ordering_when_everything_is_cached(self, client, order_response):
        for code in ("1824", "1813"):
            (client.downloads.cache_dir / f"demo_{code}.zip").write_bytes(b"cached")

        with patch("requests.post", return_value=_mock_response(order_response)) as mock_post:
            client.fetch(["1824", "1813"])

        mock_post.assert_not_called()

    def test_orders_only_what_is_missing(self, client, order_response):
        (client.downloads.cache_dir / "demo_1813.zip").write_bytes(b"cached")

        with (
            patch("requests.post", return_value=_mock_response(order_response)) as mock_post,
            patch.object(client.downloads, "download"),
        ):
            client.fetch(["1824", "1813"])

        ordered = [area["code"] for area in mock_post.call_args.kwargs["json"]["orderLines"][0]["areas"]]
        assert ordered == ["1824"]

    def test_missing_file_for_a_municipality_raises(self, client):
        payload = {"files": [{"name": "Basisdata_9999_Other.zip", "downloadUrl": "https://example.test/x"}]}

        with patch("requests.post", return_value=_mock_response(payload)), pytest.raises(LookupError, match="no file for municipality 1824"):
            client.fetch(["1824"])


class TestOrderedAt:
    """Tests for saying when the cached archives were ordered."""

    def stamp(self, client: KommuneOrderClient, code: str, when: str) -> None:
        """Write the sidecar a download would have left.

        Args:
            client: The client whose cache to write into
            code: Municipality number
            when: The moment to record
        """
        sidecar = client.downloads.cache_dir / f"{client.local_name(code)}.meta.json"
        sidecar.write_text(json.dumps({"url": "https://example.test/x", "version": "x.zip", "downloaded_at": when}))

    def test_it_reports_the_oldest_archive_in_the_cache(self, client):
        """A set of files ordered on different days is only as current as the
        one nobody re-ordered, and that is the age of the answer as a whole."""
        self.stamp(client, "1824", "2026-08-10T22:01:46")
        self.stamp(client, "1813", "2026-08-14T09:12:00")

        assert client.ordered_at(["1824", "1813"]) == "2026-08-10T22:01:46"

    def test_a_municipality_with_nothing_cached_is_passed_over(self, client):
        self.stamp(client, "1824", "2026-08-10T22:01:46")

        assert client.ordered_at(["1824", "9999"]) == "2026-08-10T22:01:46"

    def test_nothing_cached_at_all_answers_with_nothing(self, client):
        """None and not today: a date invented for an order nobody placed would
        be written into an exported file as though it were a fact."""
        assert client.ordered_at(["1824"]) is None
