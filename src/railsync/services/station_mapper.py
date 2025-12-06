"""Station mapping service for matching NS stations to Träwelling."""

import json
from pathlib import Path
from typing import Any

import structlog
from rapidfuzz import fuzz, process

from railsync.models.ns_trip import NSStation
from railsync.models.traewelling import TraewellingStation
from railsync.services.traewelling_client import TraewellingClient

logger = structlog.get_logger()


class StationMapper:
    """Map NS station names to Träwelling stations.

    Uses a combination of:
    1. Local station database (data/stations.json) with coordinates
    2. Fuzzy string matching for station name variations
    3. Träwelling API for coordinate-based lookups

    Example:
        >>> mapper = StationMapper(client, Path("data/stations.json"))
        >>> station = mapper.find_station("Amsterdam Sloterdijk")
        >>> print(f"Found: {station.name} (ID: {station.id})")
    """

    # Common abbreviations and their full forms
    ABBREVIATIONS = {
        "cs": "centraal",
        "c.": "centraal",
        "hs": "hollands spoor",
        "h.s.": "hollands spoor",
        "zw": "zwanenburg",
        "n": "noord",
        "z": "zuid",
        "o": "oost",
        "w": "west",
    }

    def __init__(
        self,
        client: TraewellingClient,
        stations_file: Path | None = None,
        cache_file: Path | None = None,
    ):
        """Initialize the station mapper.

        Args:
            client: Träwelling API client.
            stations_file: Path to stations.json file.
            cache_file: Path to cache file for Träwelling station lookups.
        """
        self.client = client
        self.stations_file = stations_file
        self.cache_file = cache_file

        # Load NS stations
        self.ns_stations: dict[str, NSStation] = {}
        if stations_file and stations_file.exists():
            self._load_ns_stations(stations_file)

        # Cache for Träwelling station lookups
        self._traewelling_cache: dict[str, TraewellingStation] = {}
        if cache_file and cache_file.exists():
            self._load_cache(cache_file)

    def _load_ns_stations(self, path: Path) -> None:
        """Load NS stations from JSON file.

        Args:
            path: Path to stations.json.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                station = NSStation.from_json(item)
                # Index by both full name and code
                self.ns_stations[station.name.lower()] = station
                self.ns_stations[station.code.lower()] = station

            logger.info("Loaded NS stations", count=len(data))
        except Exception as e:
            logger.error("Failed to load NS stations", error=str(e))

    def _load_cache(self, path: Path) -> None:
        """Load Träwelling station cache from file.

        Args:
            path: Path to cache file.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            for name, station_data in data.items():
                self._traewelling_cache[name.lower()] = TraewellingStation(**station_data)

            logger.info("Loaded station cache", count=len(data))
        except Exception as e:
            logger.warning("Failed to load station cache", error=str(e))

    def save_cache(self) -> None:
        """Save Träwelling station cache to file."""
        if not self.cache_file:
            return

        try:
            data = {
                name: station.model_dump()
                for name, station in self._traewelling_cache.items()
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            logger.info("Saved station cache", count=len(data))
        except Exception as e:
            logger.error("Failed to save station cache", error=str(e))

    def normalize_name(self, name: str) -> str:
        """Normalize station name for matching.

        Args:
            name: Raw station name from NS export.

        Returns:
            Normalized station name.
        """
        # Lowercase and strip
        normalized = name.lower().strip()

        # Remove common suffixes
        for suffix in [" (nl)", " station", " ns"]:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]

        # Expand common abbreviations
        parts = normalized.split("-")
        expanded_parts = []
        for part in parts:
            words = part.split()
            expanded_words = []
            for word in words:
                word_lower = word.lower()
                if word_lower in self.ABBREVIATIONS:
                    expanded_words.append(self.ABBREVIATIONS[word_lower])
                else:
                    expanded_words.append(word)
            expanded_parts.append(" ".join(expanded_words))

        return "-".join(expanded_parts)

    def find_ns_station(self, name: str) -> NSStation | None:
        """Find NS station by name using fuzzy matching.

        Args:
            name: Station name from NS export.

        Returns:
            Matching NSStation or None.
        """
        normalized = self.normalize_name(name)

        # Try exact match first
        if normalized in self.ns_stations:
            return self.ns_stations[normalized]

        # Try fuzzy matching
        station_names = list(self.ns_stations.keys())
        if not station_names:
            return None

        # Use rapidfuzz for fast fuzzy matching
        match = process.extractOne(
            normalized,
            station_names,
            scorer=fuzz.WRatio,
            score_cutoff=80,
        )

        if match:
            matched_name, score, _ = match
            logger.debug(
                "Fuzzy matched station",
                input=name,
                matched=matched_name,
                score=score,
            )
            return self.ns_stations[matched_name]

        return None

    def find_traewelling_station(
        self,
        name: str,
        use_coordinates: bool = True,
    ) -> TraewellingStation | None:
        """Find Träwelling station for an NS station name.

        Args:
            name: Station name from NS export.
            use_coordinates: Whether to use coordinate-based lookup.

        Returns:
            Matching TraewellingStation or None.
        """
        cache_key = name.lower()

        # Check cache first
        if cache_key in self._traewelling_cache:
            return self._traewelling_cache[cache_key]

        # Find NS station for coordinates
        ns_station = self.find_ns_station(name)

        traewelling_station: TraewellingStation | None = None

        # Try coordinate-based lookup first (most reliable)
        if use_coordinates and ns_station:
            traewelling_station = self.client.search_station_by_coordinates(
                latitude=ns_station.lat,
                longitude=ns_station.lng,
            )

        # Fallback to name-based search
        if not traewelling_station:
            search_name = ns_station.name if ns_station else name
            results = self.client.search_station_by_name(search_name)
            if results:
                traewelling_station = results[0]

        # Cache the result
        if traewelling_station:
            self._traewelling_cache[cache_key] = traewelling_station
            logger.debug(
                "Found Träwelling station",
                ns_name=name,
                traewelling_name=traewelling_station.name,
                traewelling_id=traewelling_station.id,
            )

        return traewelling_station

    def get_station_pair(
        self,
        departure_name: str,
        arrival_name: str,
    ) -> tuple[TraewellingStation | None, TraewellingStation | None]:
        """Get Träwelling stations for departure and arrival.

        Args:
            departure_name: Departure station name.
            arrival_name: Arrival station name.

        Returns:
            Tuple of (departure_station, arrival_station).
        """
        departure = self.find_traewelling_station(departure_name)
        arrival = self.find_traewelling_station(arrival_name)

        if not departure:
            logger.warning("Could not find departure station", name=departure_name)
        if not arrival:
            logger.warning("Could not find arrival station", name=arrival_name)

        return departure, arrival
