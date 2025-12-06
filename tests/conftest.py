"""Pytest fixtures for RailSync tests."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from railsync.models.ns_trip import NSTrip, TravelClass, TripType, NSExportFormat


@pytest.fixture
def sample_business_trip() -> NSTrip:
    """Create a sample business format trip."""
    return NSTrip(
        date=datetime(2025, 10, 20, 16, 7),
        check_in_time=datetime(2025, 10, 20, 16, 7),
        check_out_time=datetime(2025, 10, 20, 16, 47),
        departure_station="Den Haag",
        arrival_station="Heemstede",
        travel_class=TravelClass.FIRST,
        product="Treinreizer 1e",
        trip_type=TripType.PRIVATE,
        price=Decimal("14.97"),
        description="Check-in en -uit: Den",
        card_number="35280704",
        is_complete=True,
        source_format=NSExportFormat.BUSINESS,
    )


@pytest.fixture
def sample_consumer_trip() -> NSTrip:
    """Create a sample consumer format trip."""
    return NSTrip(
        date=datetime(2025, 9, 5, 15, 44),
        check_in_time=datetime(2025, 9, 5, 15, 44),
        check_out_time=datetime(2025, 9, 5, 16, 42),
        departure_station="Amsterdam Sloterdijk",
        arrival_station="Heiloo",
        travel_class=TravelClass.SECOND,
        product="Studenten weekabonnement Vrij Reizen",
        trip_type=TripType.PRIVATE,
        price=Decimal("0.00"),
        is_complete=True,
        source_format=NSExportFormat.CONSUMER,
    )


@pytest.fixture
def incomplete_trip() -> NSTrip:
    """Create an incomplete trip (missing check-out)."""
    return NSTrip(
        date=datetime(2025, 10, 20, 7, 20),
        check_in_time=datetime(2025, 10, 20, 7, 20),
        check_out_time=None,
        departure_station="Halfweg-Zw",
        arrival_station="Haarlem",
        travel_class=TravelClass.FIRST,
        product="Treinreizer 1e",
        trip_type=TripType.PRIVATE,
        price=Decimal("4.37"),
        description="Reis zonder check-uit",
        is_complete=False,
        source_format=NSExportFormat.BUSINESS,
    )


@pytest.fixture
def sample_trips(
    sample_business_trip: NSTrip,
    sample_consumer_trip: NSTrip,
    incomplete_trip: NSTrip,
) -> list[NSTrip]:
    """Create a list of sample trips."""
    return [sample_business_trip, sample_consumer_trip, incomplete_trip]


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_business_csv(fixtures_dir: Path, tmp_path: Path) -> Path:
    """Create a sample business CSV file."""
    content = """Dag,Datum,Product,klasse,Check in,Vertrek,Check uit,Bestemming,Omschrijving,Kenmerk,Prijs (excl.,Prijs (incl.,Prive/Zakelijk,Gefactureerd,Kaarthouder,Kaartnummer,Kaartnummer
ma,20-10-25,Treinreizer 1e,1e,16:07,Den Haag,16:47,Heemstede,Check-in en -uit: Den,,€ 14.97,,Nee,meneer S.,35280704,905453930
ma,20-10-25,Treinreizer 1e,1e,07:53,Haarlem,08:40,Den Haag,Check-in en -uit: Haar,,€ 16.22,,Nee,meneer S.,35280704,905453930
ma,20-10-25,Treinreizer 1e,1e,07:20,Halfweg-Zw,,Haarlem,Reis zonder check-uit,,€ 4.37,,Nee,meneer S.,35280704,905453930
ma,27-10-25,Correctieta,,,,,,,Correctietarief: reis zo,€ 18.35,,Nee,meneer S.,35280704,905453930"""

    csv_file = tmp_path / "business_export.csv"
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


@pytest.fixture
def sample_consumer_csv(tmp_path: Path) -> Path:
    """Create a sample consumer CSV file."""
    content = """Datum;Check in;Vertrek;Check uit;Bestemming;Af;Bij;Transactie;Kl;Product;Prive/ Zakelijk;Opmerking
5/9/2025;15:44;Amsterdam Sloterdijk;16:42;Heiloo;€0,00;€0,00;Reis;2;Studenten weekabonnement Vrij Reizen;;"""

    csv_file = tmp_path / "consumer_export.csv"
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


@pytest.fixture
def sample_stations_json(tmp_path: Path) -> Path:
    """Create a sample stations.json file."""
    import json

    stations = [
        {
            "code": "ASD",
            "name": "Amsterdam Centraal",
            "location": {"lat": 52.3788871765137, "lng": 4.90027761459351},
        },
        {
            "code": "ASS",
            "name": "Amsterdam Sloterdijk",
            "location": {"lat": 52.3888893127441, "lng": 4.83777761459351},
        },
        {
            "code": "GVC",
            "name": "Den Haag Centraal",
            "location": {"lat": 52.0808334350586, "lng": 4.32361125946045},
        },
        {
            "code": "HAD",
            "name": "Heemstede-Aerdenhout",
            "location": {"lat": 52.3591651916504, "lng": 4.60666656494141},
        },
        {
            "code": "HLM",
            "name": "Haarlem",
            "location": {"lat": 52.3877792358398, "lng": 4.63833332061768},
        },
        {
            "code": "HFZW",
            "name": "Halfweg-Zwanenburg",
            "location": {"lat": 52.3863906860352, "lng": 4.72638893127441},
        },
        {
            "code": "HLO",
            "name": "Heiloo",
            "location": {"lat": 52.6005554199219, "lng": 4.69611120223999},
        },
    ]

    stations_file = tmp_path / "stations.json"
    with open(stations_file, "w", encoding="utf-8") as f:
        json.dump(stations, f)

    return stations_file
