"""Tests for the Naturkartan link catalogue."""

import pytest
from trails.io.sources import naturkartan

CATALOGUE = """
name = "Abisko"

[[trail]]
id = "BD 21"
url = "https://www.naturkartan.se/sv/norrbottens-lan/vandringsled-bd21-fran-abisko-till-abiskojaure"

[[trail]]
id = "BD 16A"
url = "https://www.naturkartan.se/sv/norrbottens-lan/vandringsled-bd16a-fran-kopparasen-till-vadvetjakka-nationalpark"
"""


class TestLoadCatalogue:
    """The catalogue is a page per state trail number, and nothing else."""

    def test_reads_a_page_per_number_in_catalogue_order(self, tmp_path):
        path = tmp_path / "pages.toml"
        path.write_text(CATALOGUE, encoding="utf-8")

        pages = naturkartan.load_catalogue(path)

        assert list(pages) == ["BD 21", "BD 16A"]
        assert pages["BD 21"].endswith("vandringsled-bd21-fran-abisko-till-abiskojaure")

    def test_an_empty_catalogue_is_no_pages(self, tmp_path):
        path = tmp_path / "pages.toml"
        path.write_text('name = "Abisko"\n', encoding="utf-8")

        assert naturkartan.load_catalogue(path) == {}

    def test_refuses_a_link_that_is_not_http(self, tmp_path):
        """A popup writes the URL into an anchor, so the catalogue cannot be
        allowed to smuggle a `javascript:` link into the page."""
        path = tmp_path / "pages.toml"
        path.write_text('[[trail]]\nid = "BD 21"\nurl = "javascript:alert(1)"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="BD 21: url must be an http"):
            naturkartan.load_catalogue(path)

    def test_refuses_an_entry_without_a_number(self, tmp_path):
        path = tmp_path / "pages.toml"
        path.write_text('[[trail]]\nurl = "https://www.naturkartan.se/x"\n', encoding="utf-8")

        with pytest.raises(ValueError, match="no id"):
            naturkartan.load_catalogue(path)

    def test_refuses_a_number_twice(self, tmp_path):
        path = tmp_path / "pages.toml"
        path.write_text(
            '[[trail]]\nid = "BD 21"\nurl = "https://www.naturkartan.se/a"\n[[trail]]\nid = "BD 21"\nurl = "https://www.naturkartan.se/b"\n',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="appears twice"):
            naturkartan.load_catalogue(path)
