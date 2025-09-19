"""Simple hello world module for testing the package setup."""

from typing import Any


def hello_trails(name: str = "World") -> str:
    """
    Generate a greeting message for trail analysis.

    Args:
        name: Name to greet (default: "World")

    Returns:
        A greeting message string
    """
    return f"Hello {name}! Ready to analyze some trails?"


def get_sample_data() -> dict[str, Any]:
    """
    Return sample trail data for testing.

    Returns:
        Dictionary with sample trail information
    """
    return {
        "trail_name": "Sample Trail",
        "distance_km": 5.2,
        "elevation_gain_m": 250,
        "difficulty": "moderate",
        "coordinates": {
            "start": {"lat": 40.0150, "lon": -105.2705},
            "end": {"lat": 40.0251, "lon": -105.2654},
        },
    }
