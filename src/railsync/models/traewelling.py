"""Träwelling API models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Visibility(int, Enum):
    """Check-in visibility options."""

    PUBLIC = 0
    UNLISTED = 1
    FOLLOWERS = 2
    PRIVATE = 3


class BusinessType(int, Enum):
    """Business type for check-ins."""

    PRIVATE = 0
    BUSINESS = 1
    COMMUTE = 2


class TraewellingStation(BaseModel):
    """Träwelling station model."""

    id: int = Field(..., description="Träwelling internal station ID")
    name: str = Field(..., description="Station name")
    ibnr: int | None = Field(None, description="IBNR code")
    latitude: float | None = Field(None, description="Latitude")
    longitude: float | None = Field(None, description="Longitude")
    rilIdentifier: str | None = Field(None, description="RIL identifier")


class TraewellingTrip(BaseModel):
    """Träwelling trip/hafas trip model."""

    tripId: str = Field(..., description="Hafas trip ID")
    lineName: str = Field(..., description="Line name (e.g., 'IC 123')")
    origin: TraewellingStation = Field(..., description="Origin station")
    destination: TraewellingStation = Field(..., description="Destination station")
    departure: datetime = Field(..., description="Planned departure time")
    arrival: datetime = Field(..., description="Planned arrival time")


class CheckinRequest(BaseModel):
    """Request body for creating a check-in."""

    tripId: str = Field(..., description="Hafas trip ID")
    lineName: str = Field(..., description="Line name")
    start: int = Field(..., description="Start station ID or IBNR")
    destination: int = Field(..., description="Destination station ID or IBNR")
    departure: datetime = Field(..., description="Departure time (ISO 8601)")
    arrival: datetime = Field(..., description="Arrival time (ISO 8601)")
    body: str | None = Field(None, description="Status message")
    business: BusinessType = Field(BusinessType.PRIVATE, description="Business type")
    visibility: Visibility = Field(Visibility.PUBLIC, description="Status visibility")
    eventId: int | None = Field(None, description="Optional event ID")
    toot: bool = Field(False, description="Share to Mastodon")
    chainPost: bool = Field(False, description="Chain with previous status")
    ibnr: bool = Field(True, description="Whether start/destination are IBNR codes")

    model_config = ConfigDict(
        ser_json_timedelta="iso8601",
    )


class CheckinResponse(BaseModel):
    """Response from check-in endpoint."""

    id: int = Field(..., description="Status ID")
    body: str | None = Field(None, description="Status message")
    createdAt: datetime = Field(..., description="Creation timestamp")
    distance: int = Field(..., description="Trip distance in meters")
    duration: int = Field(..., description="Trip duration in minutes")
    points: int = Field(..., description="Points earned")


class UserInfo(BaseModel):
    """User information from Träwelling."""

    id: int
    displayName: str
    username: str
    profilePicture: str | None = None
    totalDistance: int = 0
    totalDuration: int = 0
    points: int = 0


class TokenResponse(BaseModel):
    """OAuth2 token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None


class DepartureInfo(BaseModel):
    """Departure information from station."""

    model_config = ConfigDict(extra="ignore")

    tripId: str = Field(..., description="Hafas trip ID")
    direction: str = Field(..., description="Direction/destination")
    plannedWhen: str | None = Field(None, description="Planned departure time (ISO string)")
    when: str | None = Field(None, description="Actual departure time (ISO string)")
    platform: str | None = Field(None, description="Platform number")
    line: dict | None = Field(None, description="Line information")

    @property
    def line_name(self) -> str:
        """Get line name from nested line object."""
        if self.line:
            return self.line.get("name", "")
        return ""

    @property
    def planned_departure(self) -> datetime | None:
        """Parse planned departure time."""
        if self.plannedWhen:
            return datetime.fromisoformat(self.plannedWhen.replace("Z", "+00:00"))
        return None
