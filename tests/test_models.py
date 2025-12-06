"""Tests for NS data models."""

from datetime import datetime
from decimal import Decimal

import pytest

from railsync.models.ns_trip import (
    NSExportFormat,
    NSStation,
    NSTrip,
    TravelClass,
    TripType,
)


class TestNSStation:
    """Tests for NSStation model."""

    def test_from_json(self) -> None:
        """Test creating NSStation from JSON data."""
        data = {
            "code": "ASD",
            "name": "Amsterdam Centraal",
            "location": {"lat": 52.378, "lng": 4.900},
        }
        station = NSStation.from_json(data)

        assert station.code == "ASD"
        assert station.name == "Amsterdam Centraal"
        assert station.lat == 52.378
        assert station.lng == 4.900


class TestNSTrip:
    """Tests for NSTrip model."""

    def test_complete_trip(self, sample_business_trip: NSTrip) -> None:
        """Test a complete trip has all fields set."""
        assert sample_business_trip.is_complete is True
        assert sample_business_trip.departure_station == "Den Haag"
        assert sample_business_trip.arrival_station == "Heemstede"
        assert sample_business_trip.travel_class == TravelClass.FIRST
        assert sample_business_trip.price == Decimal("14.97")

    def test_incomplete_trip(self, incomplete_trip: NSTrip) -> None:
        """Test an incomplete trip is marked correctly."""
        assert incomplete_trip.is_complete is False
        assert incomplete_trip.check_out_time is None

    def test_trip_serialization(self, sample_business_trip: NSTrip) -> None:
        """Test trip can be serialized to JSON."""
        data = sample_business_trip.model_dump(mode="json")

        assert data["departure_station"] == "Den Haag"
        assert data["arrival_station"] == "Heemstede"
        assert data["travel_class"] == 1
        assert data["is_complete"] is True


class TestTravelClass:
    """Tests for TravelClass enum."""

    def test_first_class(self) -> None:
        """Test first class value."""
        assert TravelClass.FIRST == 1
        assert TravelClass.FIRST.value == 1

    def test_second_class(self) -> None:
        """Test second class value."""
        assert TravelClass.SECOND == 2
        assert TravelClass.SECOND.value == 2


class TestTripType:
    """Tests for TripType enum."""

    def test_trip_types(self) -> None:
        """Test all trip types."""
        assert TripType.PRIVATE.value == "private"
        assert TripType.BUSINESS.value == "business"
        assert TripType.COMMUTE.value == "commute"


class TestNSExportFormat:
    """Tests for NSExportFormat enum."""

    def test_formats(self) -> None:
        """Test all export formats."""
        assert NSExportFormat.BUSINESS.value == "business"
        assert NSExportFormat.CONSUMER.value == "consumer"
        assert NSExportFormat.UNKNOWN.value == "unknown"
