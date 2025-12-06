"""Tests for station mapper service."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from railsync.models.traewelling import TraewellingStation
from railsync.services.station_mapper import StationMapper


class TestStationMapper:
    """Tests for StationMapper."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock Träwelling client."""
        client = MagicMock()
        client.search_station_by_coordinates.return_value = TraewellingStation(
            id=123,
            name="Amsterdam Centraal",
            ibnr=8400058,
            latitude=52.378,
            longitude=4.900,
        )
        client.search_station_by_name.return_value = [
            TraewellingStation(
                id=123,
                name="Amsterdam Centraal",
                ibnr=8400058,
            )
        ]
        return client

    @pytest.fixture
    def mapper(self, mock_client: MagicMock, sample_stations_json: Path) -> StationMapper:
        """Create a StationMapper with test data."""
        return StationMapper(
            client=mock_client,
            stations_file=sample_stations_json,
        )

    def test_load_ns_stations(self, mapper: StationMapper) -> None:
        """Test that NS stations are loaded."""
        assert len(mapper.ns_stations) > 0
        assert "amsterdam centraal" in mapper.ns_stations
        assert "asd" in mapper.ns_stations  # Code should also be indexed

    def test_normalize_name(self, mapper: StationMapper) -> None:
        """Test station name normalization."""
        # Test basic normalization
        assert mapper.normalize_name("Amsterdam Centraal") == "amsterdam centraal"

        # Test abbreviation expansion
        assert "zwanenburg" in mapper.normalize_name("Halfweg-Zw")

    def test_find_ns_station_exact_match(self, mapper: StationMapper) -> None:
        """Test finding NS station by exact name."""
        station = mapper.find_ns_station("Amsterdam Centraal")
        assert station is not None
        assert station.code == "ASD"

    def test_find_ns_station_by_code(self, mapper: StationMapper) -> None:
        """Test finding NS station by code."""
        station = mapper.find_ns_station("ASD")
        assert station is not None
        assert station.name == "Amsterdam Centraal"

    def test_find_ns_station_fuzzy_match(self, mapper: StationMapper) -> None:
        """Test fuzzy matching for station names."""
        # Should match "Heemstede-Aerdenhout"
        station = mapper.find_ns_station("Heemstede")
        assert station is not None
        assert "Heemstede" in station.name

    def test_find_ns_station_abbreviated(self, mapper: StationMapper) -> None:
        """Test finding station with abbreviated name."""
        station = mapper.find_ns_station("Halfweg-Zw")
        assert station is not None
        assert station.name == "Halfweg-Zwanenburg"

    def test_find_traewelling_station_by_coordinates(
        self, mapper: StationMapper, mock_client: MagicMock
    ) -> None:
        """Test finding Träwelling station using coordinates."""
        station = mapper.find_traewelling_station("Amsterdam Centraal")

        assert station is not None
        assert station.id == 123
        mock_client.search_station_by_coordinates.assert_called_once()

    def test_station_caching(
        self, mapper: StationMapper, mock_client: MagicMock
    ) -> None:
        """Test that station lookups are cached."""
        # First lookup
        station1 = mapper.find_traewelling_station("Amsterdam Centraal")

        # Second lookup should use cache
        station2 = mapper.find_traewelling_station("Amsterdam Centraal")

        assert station1 == station2
        # Should only call API once
        assert mock_client.search_station_by_coordinates.call_count == 1

    def test_get_station_pair(
        self, mapper: StationMapper, mock_client: MagicMock
    ) -> None:
        """Test getting departure and arrival station pair."""
        departure, arrival = mapper.get_station_pair(
            "Amsterdam Centraal",
            "Haarlem",
        )

        assert departure is not None
        assert arrival is not None

    def test_find_station_not_found(
        self, mapper: StationMapper, mock_client: MagicMock
    ) -> None:
        """Test handling station not found."""
        mock_client.search_station_by_coordinates.return_value = None
        mock_client.search_station_by_name.return_value = []

        station = mapper.find_traewelling_station("NonexistentStation")
        assert station is None


class TestStationNameNormalization:
    """Tests for station name normalization."""

    @pytest.fixture
    def mapper(self) -> StationMapper:
        """Create mapper without loading stations."""
        mock_client = MagicMock()
        return StationMapper(client=mock_client)

    def test_lowercase_and_strip(self, mapper: StationMapper) -> None:
        """Test basic normalization."""
        assert mapper.normalize_name("  Amsterdam  ") == "amsterdam"

    def test_remove_nl_suffix(self, mapper: StationMapper) -> None:
        """Test removing (NL) suffix."""
        assert mapper.normalize_name("Amsterdam (NL)") == "amsterdam"

    def test_expand_cs_abbreviation(self, mapper: StationMapper) -> None:
        """Test expanding CS abbreviation."""
        result = mapper.normalize_name("Amsterdam CS")
        assert "centraal" in result

    def test_expand_hs_abbreviation(self, mapper: StationMapper) -> None:
        """Test expanding HS abbreviation."""
        result = mapper.normalize_name("Den Haag HS")
        assert "hollands spoor" in result
