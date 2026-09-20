import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common.validation import normalize_location, validate_request


def test_normalizes_nyc():
    assert normalize_location("nyc") == "New York City"


def test_valid_payload():
    result = validate_request(
        {
            "location": "brooklyn",
            "cuisine": "indian",
            "date": "2027-06-10",
            "time": "19:30",
            "party_size": 4,
            "email": "demo@example.com",
        }
    )
    assert result["location"] == "Brooklyn"
    assert result["cuisine"] == "Indian"
    assert result["party_size"] == 4


def test_rejects_bad_party_size():
    try:
        validate_request(
            {
                "location": "Manhattan",
                "cuisine": "Italian",
                "date": "2027-06-10",
                "time": "19:30",
                "party_size": 0,
                "email": "demo@example.com",
            }
        )
    except ValueError as exc:
        assert "party_size" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
