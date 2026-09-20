from __future__ import annotations

from datetime import datetime
from typing import Any

ALLOWED_CUISINES = {
    "american", "chinese", "french", "greek", "indian", "italian",
    "japanese", "korean", "mediterranean", "mexican", "thai", "vietnamese",
}

NYC_LOCATION_ALIASES = {
    "nyc": "New York City",
    "new york": "New York City",
    "new york city": "New York City",
    "manhattan": "Manhattan",
    "brooklyn": "Brooklyn",
    "queens": "Queens",
    "bronx": "Bronx",
    "staten island": "Staten Island",
}


def normalize_location(value: str) -> str:
    cleaned = " ".join(value.strip().lower().split())
    return NYC_LOCATION_ALIASES.get(cleaned, value.strip().title())


def validate_request(payload: dict[str, Any]) -> dict[str, Any]:
    required = ["location", "cuisine", "date", "time", "party_size", "email"]
    missing = [key for key in required if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    email = str(payload["email"]).strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Please provide a valid email address.")

    cuisine = str(payload["cuisine"]).strip().lower()
    if cuisine not in ALLOWED_CUISINES:
        raise ValueError(
            "Unsupported cuisine. Choose one of: " + ", ".join(sorted(ALLOWED_CUISINES))
        )

    try:
        party_size = int(payload["party_size"])
    except (TypeError, ValueError) as exc:
        raise ValueError("party_size must be a number.") from exc
    if party_size < 1 or party_size > 20:
        raise ValueError("party_size must be between 1 and 20.")

    try:
        dining_date = datetime.strptime(str(payload["date"]), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD.") from exc

    try:
        datetime.strptime(str(payload["time"]), "%H:%M")
    except ValueError as exc:
        raise ValueError("time must use 24-hour HH:MM format.") from exc

    return {
        "location": normalize_location(str(payload["location"])),
        "cuisine": cuisine.title(),
        "date": dining_date.isoformat(),
        "time": str(payload["time"]),
        "party_size": party_size,
        "email": email,
    }
