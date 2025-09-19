"""Pytest configuration and shared fixtures for trails tests."""

import sys
from pathlib import Path
from typing import Any

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_trail_data() -> dict[str, Any]:
    """Fixture providing sample trail data for tests."""
    return {
        "trail_name": "Test Trail",
        "distance_km": 10.5,
        "elevation_gain_m": 500,
        "difficulty": "moderate",
        "coordinates": {
            "start": {"lat": 40.0, "lon": -105.0},
            "end": {"lat": 40.1, "lon": -105.1},
        },
    }


@pytest.fixture
def sample_gpx_content() -> str:
    """Fixture providing sample GPX file content for tests."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="trails-test">
    <trk>
        <name>Test Trail</name>
        <trkseg>
            <trkpt lat="40.0" lon="-105.0">
                <ele>2500</ele>
            </trkpt>
            <trkpt lat="40.1" lon="-105.1">
                <ele>2600</ele>
            </trkpt>
        </trkseg>
    </trk>
</gpx>"""
