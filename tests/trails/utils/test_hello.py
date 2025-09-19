"""Tests for the trails.utils.hello module."""

import pytest

from trails.utils.hello import get_sample_data, hello_trails


class TestHelloTrails:
    """Test suite for the hello_trails function."""

    def test_hello_trails_default(self) -> None:
        """Test hello_trails with default parameter."""
        result = hello_trails()
        assert result == "Hello World! Ready to analyze some trails?"
        assert isinstance(result, str)

    def test_hello_trails_with_name(self) -> None:
        """Test hello_trails with custom name."""
        result = hello_trails("Hiker")
        assert result == "Hello Hiker! Ready to analyze some trails?"
        assert "Hiker" in result

    def test_hello_trails_empty_string(self) -> None:
        """Test hello_trails with empty string."""
        result = hello_trails("")
        assert result == "Hello ! Ready to analyze some trails?"

    def test_hello_trails_special_characters(self) -> None:
        """Test hello_trails with special characters."""
        result = hello_trails("Trail-Runner123")
        assert result == "Hello Trail-Runner123! Ready to analyze some trails?"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Alice", "Hello Alice! Ready to analyze some trails?"),
            ("Bob", "Hello Bob! Ready to analyze some trails?"),
            ("Test User", "Hello Test User! Ready to analyze some trails?"),
            ("123", "Hello 123! Ready to analyze some trails?"),
        ],
    )
    def test_hello_trails_parametrized(self, name: str, expected: str) -> None:
        """Test hello_trails with various inputs using parametrization."""
        assert hello_trails(name) == expected


class TestGetSampleData:
    """Test suite for the get_sample_data function."""

    def test_get_sample_data_structure(self) -> None:
        """Test that get_sample_data returns correct structure."""
        data = get_sample_data()

        # Check it returns a dictionary
        assert isinstance(data, dict)

        # Check required keys exist
        required_keys = {
            "trail_name",
            "distance_km",
            "elevation_gain_m",
            "difficulty",
            "coordinates",
        }
        assert set(data.keys()) == required_keys

    def test_get_sample_data_values(self) -> None:
        """Test that get_sample_data returns expected values."""
        data = get_sample_data()

        assert data["trail_name"] == "Sample Trail"
        assert data["distance_km"] == 5.2
        assert data["elevation_gain_m"] == 250
        assert data["difficulty"] == "moderate"

    def test_get_sample_data_coordinates(self) -> None:
        """Test coordinate structure in sample data."""
        data = get_sample_data()
        coordinates = data["coordinates"]

        # Check coordinates structure
        assert isinstance(coordinates, dict)
        assert "start" in coordinates
        assert "end" in coordinates

        # Check start coordinates
        start = coordinates["start"]
        assert isinstance(start, dict)
        assert start["lat"] == 40.0150
        assert start["lon"] == -105.2705

        # Check end coordinates
        end = coordinates["end"]
        assert isinstance(end, dict)
        assert end["lat"] == 40.0251
        assert end["lon"] == -105.2654

    def test_get_sample_data_types(self) -> None:
        """Test that get_sample_data returns correct data types."""
        data = get_sample_data()

        assert isinstance(data["trail_name"], str)
        assert isinstance(data["distance_km"], (int, float))
        assert isinstance(data["elevation_gain_m"], int)
        assert isinstance(data["difficulty"], str)
        assert isinstance(data["coordinates"], dict)

    def test_get_sample_data_immutability(self) -> None:
        """Test that get_sample_data returns a new dict each time."""
        data1 = get_sample_data()
        data2 = get_sample_data()

        # They should be equal but not the same object
        assert data1 == data2
        assert data1 is not data2

        # Modifying one should not affect the other
        data1["trail_name"] = "Modified Trail"
        assert data2["trail_name"] == "Sample Trail"

    def test_get_sample_data_coordinate_validity(self) -> None:
        """Test that coordinates are valid latitude/longitude values."""
        data = get_sample_data()

        start_lat = data["coordinates"]["start"]["lat"]
        start_lon = data["coordinates"]["start"]["lon"]
        end_lat = data["coordinates"]["end"]["lat"]
        end_lon = data["coordinates"]["end"]["lon"]

        # Check latitude bounds (-90 to 90)
        assert -90 <= start_lat <= 90
        assert -90 <= end_lat <= 90

        # Check longitude bounds (-180 to 180)
        assert -180 <= start_lon <= 180
        assert -180 <= end_lon <= 180
