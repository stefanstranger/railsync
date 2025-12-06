"""Tests for NS export parsers."""

from pathlib import Path

import pandas as pd
import pytest

from railsync.models.ns_trip import NSExportFormat, TravelClass
from railsync.parsers.base import ParseError, detect_format
from railsync.parsers.business_parser import BusinessParser
from railsync.parsers.consumer_parser import ConsumerParser


class TestFormatDetection:
    """Tests for format detection."""

    def test_detect_business_format(self) -> None:
        """Test detecting business format by Dag column."""
        df = pd.DataFrame({
            "Dag": ["ma", "di"],
            "Datum": ["20-10-25", "21-10-25"],
            "Vertrek": ["Amsterdam", "Rotterdam"],
        })
        assert detect_format(df) == NSExportFormat.BUSINESS

    def test_detect_consumer_format(self) -> None:
        """Test detecting consumer format by Transactie column."""
        df = pd.DataFrame({
            "Datum": ["5/9/2025"],
            "Vertrek": ["Amsterdam"],
            "Transactie": ["Reis"],
            "Kl": [2],
        })
        assert detect_format(df) == NSExportFormat.CONSUMER

    def test_detect_unknown_format(self) -> None:
        """Test detecting unknown format."""
        df = pd.DataFrame({
            "Column1": ["value1"],
            "Column2": ["value2"],
        })
        assert detect_format(df) == NSExportFormat.UNKNOWN


class TestBusinessParser:
    """Tests for BusinessParser."""

    def test_can_parse_business_format(self) -> None:
        """Test parser recognizes business format."""
        parser = BusinessParser()
        df = pd.DataFrame({
            "Dag": ["ma"],
            "Datum": ["20-10-25"],
            "Vertrek": ["Den Haag"],
        })
        assert parser.can_parse(df) is True

    def test_cannot_parse_consumer_format(self) -> None:
        """Test parser rejects consumer format."""
        parser = BusinessParser()
        df = pd.DataFrame({
            "Datum": ["5/9/2025"],
            "Transactie": ["Reis"],
        })
        assert parser.can_parse(df) is False

    def test_parse_business_csv(self, sample_business_csv: Path) -> None:
        """Test parsing business CSV file."""
        parser = BusinessParser()
        trips = parser.parse(sample_business_csv)

        # Should have 2 valid trips (correction row skipped, one incomplete)
        assert len(trips) >= 2

        # Check first trip
        trip = trips[0]
        assert trip.departure_station == "Den Haag"
        assert trip.arrival_station == "Heemstede"
        assert trip.travel_class == TravelClass.FIRST
        assert trip.is_complete is True

    def test_skip_correction_rows(self, sample_business_csv: Path) -> None:
        """Test that correction rows are skipped."""
        parser = BusinessParser()
        trips = parser.parse(sample_business_csv)

        # No trip should have "Correctie" in product
        for trip in trips:
            assert "correctie" not in trip.product.lower()

    def test_parse_incomplete_trip(self, sample_business_csv: Path) -> None:
        """Test parsing incomplete trips."""
        parser = BusinessParser()
        trips = parser.parse(sample_business_csv)

        # Find the incomplete trip
        incomplete = [t for t in trips if not t.is_complete]
        assert len(incomplete) == 1
        assert incomplete[0].departure_station == "Halfweg-Zw"


class TestConsumerParser:
    """Tests for ConsumerParser."""

    def test_can_parse_consumer_format(self) -> None:
        """Test parser recognizes consumer format."""
        parser = ConsumerParser()
        df = pd.DataFrame({
            "Datum": ["5/9/2025"],
            "Transactie": ["Reis"],
            "Kl": [2],
        })
        assert parser.can_parse(df) is True

    def test_cannot_parse_business_format(self) -> None:
        """Test parser rejects business format."""
        parser = ConsumerParser()
        df = pd.DataFrame({
            "Dag": ["ma"],
            "Gefactureerd": ["Nee"],
        })
        assert parser.can_parse(df) is False

    def test_parse_consumer_csv(self, sample_consumer_csv: Path) -> None:
        """Test parsing consumer CSV file."""
        parser = ConsumerParser()
        trips = parser.parse(sample_consumer_csv)

        assert len(trips) == 1

        trip = trips[0]
        assert trip.departure_station == "Amsterdam Sloterdijk"
        assert trip.arrival_station == "Heiloo"
        assert trip.travel_class == TravelClass.SECOND
        assert trip.is_complete is True


class TestDateParsing:
    """Tests for date parsing in parsers."""

    def test_business_date_format(self) -> None:
        """Test parsing DD-MM-YY format."""
        parser = BusinessParser()
        dt = parser._parse_datetime("20-10-25", "16:07")

        assert dt.year == 2025
        assert dt.month == 10
        assert dt.day == 20
        assert dt.hour == 16
        assert dt.minute == 7

    def test_consumer_date_format(self) -> None:
        """Test parsing M/D/YYYY format."""
        parser = ConsumerParser()
        dt = parser._parse_datetime("5/9/2025", "15:44")

        assert dt.year == 2025
        assert dt.month == 5
        assert dt.day == 9
        assert dt.hour == 15
        assert dt.minute == 44

    def test_invalid_date_raises_error(self) -> None:
        """Test that invalid dates raise ValueError."""
        parser = BusinessParser()

        with pytest.raises(ValueError):
            parser._parse_datetime("invalid", "16:07")

    def test_invalid_time_raises_error(self) -> None:
        """Test that invalid times raise ValueError."""
        parser = BusinessParser()

        with pytest.raises(ValueError):
            parser._parse_datetime("20-10-25", "invalid")
