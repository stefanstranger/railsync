"""NS travel data models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TravelClass(int, Enum):
    """Travel class enumeration."""

    SECOND = 2
    FIRST = 1


class TripType(str, Enum):
    """Trip type classification."""

    PRIVATE = "private"
    BUSINESS = "business"
    COMMUTE = "commute"


class NSStation(BaseModel):
    """NS Station model from stations.json."""

    code: str = Field(..., description="NS station code (e.g., 'ASD')")
    name: str = Field(..., description="Full station name")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")

    @classmethod
    def from_json(cls, data: dict) -> "NSStation":
        """Create NSStation from JSON data."""
        return cls(
            code=data["code"],
            name=data["name"],
            lat=data["location"]["lat"],
            lng=data["location"]["lng"],
        )


class NSTrip(BaseModel):
    """Represents a single trip from NS export data."""

    # Date and time
    date: datetime = Field(..., description="Travel date")
    check_in_time: datetime = Field(..., description="Check-in datetime")
    check_out_time: datetime | None = Field(
        None, description="Check-out datetime (None if missing)"
    )

    # Stations
    departure_station: str = Field(..., description="Departure station name from NS")
    arrival_station: str | None = Field(
        None, description="Arrival station name (None if missing check-out)"
    )

    # Trip details
    travel_class: TravelClass = Field(
        TravelClass.SECOND, description="Travel class (1 or 2)"
    )
    product: str = Field(..., description="NS product/subscription name")
    trip_type: TripType = Field(TripType.PRIVATE, description="Trip type")

    # Pricing
    price: Decimal | None = Field(None, description="Trip price in EUR")

    # Metadata
    description: str | None = Field(None, description="Trip description")
    card_number: str | None = Field(None, description="NS Business Card number")
    is_complete: bool = Field(True, description="Whether trip has both check-in/out")

    # Source format tracking
    source_format: str = Field("unknown", description="Source format: business or consumer")

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )


class NSExportFormat(str, Enum):
    """NS export format type."""

    BUSINESS = "business"  # XLS from Mijn NS Zakelijk
    CONSUMER = "consumer"  # CSV from NS App
    UNKNOWN = "unknown"
