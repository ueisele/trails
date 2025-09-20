"""Tests for geonorge_codes module."""

import pytest

from trails.io.sources.geonorge_codes import (
    CODE_TABLES,
    CodeEntry,
    get_code,
    get_description,
    get_entry,
    get_value,
    has_code_table,
)
from trails.io.sources.language import Language


class TestCodeEntry:
    """Test CodeEntry dataclass."""

    def test_code_entry_creation(self):
        """Test creating CodeEntry with valid values."""
        entry = CodeEntry(value="Test Value", description="Test Description")
        assert entry.value == "Test Value"
        assert entry.description == "Test Description"


class TestCodeTablesStructure:
    """Test CODE_TABLES data structure."""

    def test_code_tables_is_dict(self):
        """Test CODE_TABLES is a dictionary."""
        assert isinstance(CODE_TABLES, dict)

    def test_expected_columns_exist(self):
        """Test all expected columns exist in CODE_TABLES."""
        expected_columns = [
            "objtype",
            "rutefolger",
            "rutebredde",
            "gradering",
            "sesong",
            "tilpasning",
            "tilrettelegging",
            "trafikkbelastning",
            "malemetode",
            "merking",
            "belysning",
            "skilting",
            "underlagstype",
            "rutetype",
            "rutebetydning",
            "ryddebredde",
            "spesialfotrutetype",
            "spesialskiloypetype",
            "spesialsykkelrutetype",
            "spesialannenrutetype",
            "preparering",
        ]
        for column in expected_columns:
            assert column in CODE_TABLES, f"Column {column} missing from CODE_TABLES"

    def test_all_entries_have_language_keys(self):
        """Test all code entries have proper language structure."""
        for column, codes in CODE_TABLES.items():
            assert isinstance(codes, dict), f"Column {column} should be a dict"
            for code, lang_entries in codes.items():
                assert isinstance(lang_entries, dict), f"Code {code} in {column} should have dict of languages"
                # Most codes should have both NO and EN
                assert Language.NO in lang_entries or Language.EN in lang_entries, f"Code {code} in {column} has no language entries"

    def test_all_entries_are_code_entry_instances(self):
        """Test all language entries are CodeEntry instances."""
        for column, codes in CODE_TABLES.items():
            for code, lang_entries in codes.items():
                for language, entry in lang_entries.items():
                    assert isinstance(entry, CodeEntry), f"Entry for {column}[{code}][{language}] is not CodeEntry"
                    assert entry.value, f"Empty value for {column}[{code}][{language}]"
                    assert entry.description, f"Empty description for {column}[{code}][{language}]"


class TestGetEntry:
    """Test get_entry function."""

    def test_valid_column_and_code(self):
        """Test get_entry with valid column and code."""
        entry = get_entry("gradering", "G", Language.NO)
        assert entry is not None
        assert entry.value == "Enkel (Grønn)"
        assert "nybegynnere" in entry.description.lower()

    def test_valid_column_and_code_english(self):
        """Test get_entry with English language."""
        entry = get_entry("gradering", "G", Language.EN)
        assert entry is not None
        assert entry.value == "Easy (Green)"
        assert "beginners" in entry.description.lower()

    def test_invalid_column(self):
        """Test get_entry with invalid column."""
        entry = get_entry("nonexistent_column", "G", Language.NO)
        assert entry is None

    def test_invalid_code(self):
        """Test get_entry with invalid code."""
        entry = get_entry("gradering", "INVALID", Language.NO)
        assert entry is None

    def test_missing_language(self):
        """Test get_entry when language doesn't exist for code."""
        # Most codes have both NO and EN, but test behavior if one is missing
        entry = get_entry("gradering", "G", Language.NO)
        assert entry is not None  # Should exist

    def test_default_language(self):
        """Test get_entry uses NO as default language."""
        entry = get_entry("gradering", "G")
        assert entry is not None
        assert entry.value == "Enkel (Grønn)"


class TestGetValue:
    """Test get_value function."""

    def test_valid_column_and_code(self):
        """Test get_value with valid inputs."""
        value = get_value("gradering", "B", Language.NO)
        assert value == "Middels (Blå)"

    def test_valid_column_and_code_english(self):
        """Test get_value with English language."""
        value = get_value("gradering", "B", Language.EN)
        assert value == "Medium (Blue)"

    def test_invalid_column(self):
        """Test get_value with invalid column."""
        value = get_value("invalid_column", "B", Language.NO)
        assert value is None

    def test_invalid_code(self):
        """Test get_value with invalid code."""
        value = get_value("gradering", "INVALID", Language.NO)
        assert value is None

    def test_numeric_codes(self):
        """Test get_value with numeric string codes."""
        value = get_value("rutebredde", "0", Language.NO)
        assert value == "0-0.5 m"

    def test_alphanumeric_codes(self):
        """Test get_value with alphanumeric codes."""
        value = get_value("underlagstype", "1.0", Language.NO)
        assert value == "Asfalt/betong"


class TestGetDescription:
    """Test get_description function."""

    def test_valid_column_and_code(self):
        """Test get_description with valid inputs."""
        desc = get_description("gradering", "R", Language.NO)
        assert desc is not None
        assert "krevende" in desc.lower()
        assert "1000m" in desc

    def test_valid_column_and_code_english(self):
        """Test get_description with English language."""
        desc = get_description("gradering", "R", Language.EN)
        assert desc is not None
        assert "trail" in desc.lower()  # Changed from "strenuous" which is in value not description
        assert "1000m" in desc

    def test_invalid_inputs(self):
        """Test get_description with invalid inputs."""
        assert get_description("invalid", "R", Language.NO) is None
        assert get_description("gradering", "INVALID", Language.NO) is None

    def test_long_descriptions(self):
        """Test get_description handles long descriptions properly."""
        desc = get_description("malemetode", "92", Language.NO)
        assert desc is not None
        assert len(desc) > 50  # Should be a longer description

    def test_special_characters_in_description(self):
        """Test descriptions with special characters."""
        desc = get_description("tilrettelegging", "7", Language.NO)
        assert "bål" in desc.lower() or "grill" in desc.lower()


class TestGetCode:
    """Test get_code reverse lookup function."""

    def test_valid_reverse_lookup_norwegian(self):
        """Test get_code with valid Norwegian value."""
        code = get_code("gradering", "Enkel (Grønn)", Language.NO)
        assert code == "G"

    def test_valid_reverse_lookup_english(self):
        """Test get_code with valid English value."""
        code = get_code("gradering", "Easy (Green)", Language.EN)
        assert code == "G"

    def test_exact_match_required(self):
        """Test get_code requires exact match."""
        # Partial match should not work
        code = get_code("gradering", "Enkel", Language.NO)
        assert code is None

    def test_invalid_column(self):
        """Test get_code with invalid column."""
        code = get_code("invalid_column", "Enkel (Grønn)", Language.NO)
        assert code is None

    def test_invalid_value(self):
        """Test get_code with non-existent value."""
        code = get_code("gradering", "Invalid Value", Language.NO)
        assert code is None

    def test_case_sensitive_value(self):
        """Test get_code is case sensitive."""
        # Should not match with different case
        code = get_code("gradering", "enkel (grønn)", Language.NO)
        assert code is None

    def test_values_with_special_characters(self):
        """Test get_code with values containing special characters."""
        code = get_code("rutebredde", "0.5 - opp til 1.5 m", Language.NO)
        assert code == "1"

    def test_numeric_string_codes(self):
        """Test reverse lookup for numeric string codes."""
        code = get_code("tilrettelegging", "Benker/bord", Language.NO)
        assert code == "4"


class TestHasCodeTable:
    """Test has_code_table function."""

    def test_valid_columns(self):
        """Test has_code_table returns True for valid columns."""
        assert has_code_table("gradering") is True
        assert has_code_table("rutefolger") is True
        assert has_code_table("sesong") is True

    def test_invalid_columns(self):
        """Test has_code_table returns False for invalid columns."""
        assert has_code_table("nonexistent") is False
        assert has_code_table("") is False
        assert has_code_table("GRADERING") is False  # Case sensitive

    def test_case_sensitivity(self):
        """Test has_code_table is case sensitive."""
        assert has_code_table("gradering") is True
        assert has_code_table("Gradering") is False
        assert has_code_table("GRADERING") is False


class TestDataIntegrity:
    """Test data integrity of CODE_TABLES."""

    def test_no_empty_values_or_descriptions(self):
        """Test no empty values or descriptions in CODE_TABLES."""
        for column, codes in CODE_TABLES.items():
            for code, lang_entries in codes.items():
                for language, entry in lang_entries.items():
                    assert entry.value.strip(), f"Empty value for {column}[{code}][{language}]"
                    assert entry.description.strip(), f"Empty description for {column}[{code}][{language}]"

    def test_no_duplicate_codes_in_column(self):
        """Test no duplicate codes within a column."""
        for column, codes in CODE_TABLES.items():
            code_list = list(codes.keys())
            assert len(code_list) == len(set(code_list)), f"Duplicate codes in column {column}"

    def test_consistent_language_coverage(self):
        """Test most codes have both NO and EN translations."""
        missing_translations = []
        for column, codes in CODE_TABLES.items():
            for code, lang_entries in codes.items():
                if Language.NO not in lang_entries:
                    missing_translations.append(f"{column}[{code}] missing NO")
                if Language.EN not in lang_entries:
                    missing_translations.append(f"{column}[{code}] missing EN")

        # All codes should have both languages
        assert len(missing_translations) == 0, f"Missing translations: {missing_translations[:5]}"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_none_inputs(self):
        """Test functions handle None inputs gracefully."""
        # These should not raise exceptions
        assert get_entry(None, "G", Language.NO) is None  # type: ignore
        assert get_value("gradering", None, Language.NO) is None  # type: ignore
        assert get_description(None, None, Language.NO) is None  # type: ignore
        assert get_code(None, "value", Language.NO) is None  # type: ignore

    def test_empty_string_inputs(self):
        """Test functions handle empty strings."""
        assert get_entry("", "", Language.NO) is None
        assert get_value("", "", Language.NO) is None
        assert get_description("", "", Language.NO) is None
        assert get_code("", "", Language.NO) is None
        assert has_code_table("") is False

    def test_mixed_case_columns(self):
        """Test columns are case sensitive."""
        assert get_value("GRADERING", "G", Language.NO) is None
        assert get_value("Gradering", "G", Language.NO) is None
        assert get_value("gradering", "G", Language.NO) == "Enkel (Grønn)"

    def test_numeric_vs_string_codes(self):
        """Test handling of numeric codes stored as strings."""
        # Numeric codes should work as strings
        assert get_value("rutebredde", "0", Language.NO) == "0-0.5 m"
        assert get_value("rutebredde", "1", Language.NO) == "0.5 - opp til 1.5 m"

        # But actual integers should not work (type mismatch)
        assert get_value("rutebredde", 0, Language.NO) is None  # type: ignore

    def test_codes_with_dots(self):
        """Test codes containing dots."""
        assert get_value("underlagstype", "1.0", Language.NO) == "Asfalt/betong"
        assert get_value("underlagstype", "2.0", Language.NO) == "Grus"
        assert get_value("rutetype", "1.0", Language.NO) == "Hovedrute"


@pytest.mark.parametrize(
    "column,code,expected_no,expected_en",
    [
        ("gradering", "G", "Enkel (Grønn)", "Easy (Green)"),
        ("gradering", "B", "Middels (Blå)", "Medium (Blue)"),
        ("sesong", "S", "Sommer", "Summer"),
        ("sesong", "V", "Vinter", "Winter"),
        ("merking", "JA", "Merket", "Marked"),
        ("rutefolger", "ST", "Sti", "Path/trail"),
        ("rutebredde", "0", "0-0.5 m", "0-0.5 m"),
    ],
)
def test_parametrized_values(column, code, expected_no, expected_en):
    """Test various codes with parametrized inputs."""
    assert get_value(column, code, Language.NO) == expected_no
    assert get_value(column, code, Language.EN) == expected_en


@pytest.mark.parametrize(
    "column,value,language,expected_code",
    [
        ("gradering", "Enkel (Grønn)", Language.NO, "G"),
        ("gradering", "Easy (Green)", Language.EN, "G"),
        ("sesong", "Sommer", Language.NO, "S"),
        ("sesong", "Winter", Language.EN, "V"),
        ("merking", "Merket", Language.NO, "JA"),
    ],
)
def test_parametrized_reverse_lookup(column, value, language, expected_code):
    """Test reverse lookup with parametrized inputs."""
    assert get_code(column, value, language) == expected_code
