# RailSync - Coding Agent Instructions

> Import NS travel data into Träwelling to earn points and share your train journeys.

## Project Overview

RailSync is a Python solution that imports travel data from Nederlandse Spoorwegen (NS) and creates check-ins on Träwelling. The tool reads CSV/XLS exports from "Mijn NS Zakelijk" and uses the Träwelling API to automatically log journeys.

### Core Functionality

1. **Parse NS Travel Data**: Read and parse CSV/XLS files exported from Mijn NS Zakelijk
2. **Station Mapping**: Map NS station names to Träwelling station IDs (IBNR codes)
3. **Träwelling Integration**: Authenticate via OAuth2 and create check-ins via the API
4. **Validation & Deduplication**: Prevent duplicate check-ins and validate trip data

---

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: `uv` (preferred) - fast Python package installer and resolver
- **HTTP Client**: `httpx` or `requests` for API calls
- **Data Processing**: `pandas` for CSV/XLS parsing
- **Configuration**: Environment variables via `python-dotenv`
- **Testing**: `pytest` with `pytest-cov` for coverage
- **Linting**: `ruff` for linting and formatting
- **Type Checking**: `mypy` for static type analysis
- **Future Web Framework**: FastAPI (for Azure Web App deployment)

---

## Project Structure

```
railsync/
├── .github/
│   ├── copilot-instructions.md    # This file
│   └── workflows/                  # GitHub Actions CI/CD
├── src/
│   └── railsync/
│       ├── __init__.py
│       ├── main.py                 # CLI entry point
│       ├── config.py               # Configuration management
│       ├── models/
│       │   ├── __init__.py
│       │   ├── ns_trip.py          # NS travel data models
│       │   └── traewelling.py      # Träwelling API models
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── csv_parser.py       # NS CSV file parser
│       │   └── xls_parser.py       # NS XLS file parser
│       ├── services/
│       │   ├── __init__.py
│       │   ├── traewelling_client.py  # Träwelling API client
│       │   ├── station_mapper.py      # Station name to ID mapping
│       │   └── checkin_service.py     # Check-in orchestration
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # pytest fixtures
│   ├── test_parsers/
│   ├── test_services/
│   └── test_models/
├── data/
│   └── stations.json               # Station name to IBNR mapping cache
├── .env.example
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## Träwelling API Reference

### Authentication

Träwelling uses **OAuth2** for authentication. The legacy login endpoints have been deprecated.

1. **Register Application**: Create an OAuth application at https://traewelling.de/settings/applications
2. **Authorization Flow**: Use authorization code grant for user authentication
3. **Token Usage**: Include bearer token in Authorization header

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}
```

### Key Endpoints

#### Check-in Endpoint
```
POST /api/v1/trains/checkin
```

**Request Body Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `tripId` | string | Yes | The Hafas trip ID |
| `lineName` | string | Yes | Line name (e.g., "IC 123") |
| `start` | integer | Yes | Träwelling station ID or IBNR |
| `destination` | integer | Yes | Träwelling station ID or IBNR |
| `departure` | string | Yes | ISO 8601 departure time |
| `arrival` | string | Yes | ISO 8601 arrival time |
| `body` | string | No | Status message |
| `business` | integer | No | 0=private, 1=business, 2=commute |
| `visibility` | integer | No | 0=public, 1=unlisted, 2=followers, 3=private |
| `eventId` | integer | No | Event ID if checking in to an event |

#### Station Search
```
GET /api/v1/station/autocomplete/{query}
```

#### Get Departures
```
GET /api/v1/station/{id}/departures
```

### API Changelog Notes

- Use `manualDeparture` and `manualArrival` (not `overriddenDeparture`/`overriddenArrival`)
- Use `totalDuration` and `totalDistance` (not `trainDuration`/`trainDistance`)
- Station endpoints use Träwelling internal IDs, not IBNR directly

---

## NS Travel Data Format

RailSync supports two different NS export formats: **Business (XLS)** from Mijn NS Zakelijk and **Consumer (CSV)** from the regular NS app/website.

### Format 1: Business Export (XLS) - Mijn NS Zakelijk

The export from "Mijn NS Zakelijk" contains travel transactions with these columns:

| Column (Dutch) | Column (English) | Example | Description |
|----------------|------------------|---------|-------------|
| Dag | Day | ma, di, wo | Day of the week (Dutch abbreviation) |
| Datum | Date | 20-10-25 | Travel date (DD-MM-YY format) |
| Product | Product | Treinreizer 1e | Subscription/product + class |
| klasse | Class | 1e | Travel class (1e/2e = first/second) |
| Check in | Check-in time | 16:07 | Time of check-in (HH:MM) |
| Vertrek | Departure | Den Haag | Departure station name |
| Check uit | Check-out time | 16:47 | Time of check-out (HH:MM) |
| Bestemming | Destination | Heemstede | Arrival station name |
| Omschrijving | Description | Check-in en -uit: Den | Trip description |
| Kenmerk | Marker | - | Custom trip marker/label |
| Prijs (excl. | Price excl. | € 14.97 | Price excluding VAT |
| Prijs (incl. | Price incl. | - | Price including VAT |
| Prive/Zakelijk | Private/Business | - | Trip type classification |
| Gefactureerd | Invoiced | Nee | Whether invoiced (Ja/Nee) |
| Kaarthouder | Cardholder | meneer S. | Cardholder name |
| Kaartnummer | Card number | 35280704 | NS Business Card number |
| Kaartnummer | Card number (full) | 905453930 | Full card number |

### Format 2: Consumer Export (CSV) - NS App/Website

The export from NS for consumers has a simpler structure:

| Column (Dutch) | Column (English) | Example | Description |
|----------------|------------------|---------|-------------|
| Datum | Date | 5/9/2025 | Travel date (M/D/YYYY format) |
| Check in | Check-in time | 15:44 | Time of check-in (HH:MM) |
| Vertrek | Departure | Amsterdam Sloterdijk | Departure station name |
| Check uit | Check-out time | 16:42 | Time of check-out (HH:MM) |
| Bestemming | Destination | Heiloo | Arrival station name |
| Af | Amount deducted | €0,00 | Amount charged (with € symbol) |
| Bij | Amount added | €0,00 | Amount credited |
| Transactie | Transaction | Reis | Transaction type |
| Kl | Class | 2 | Travel class (1 or 2) |
| Product | Product | Studenten weekabonnement Vrij Reizen | Subscription name |
| Prive/Zakelijk | Private/Business | - | Trip type |
| Opmerking | Remarks | - | Additional notes |

### Format Differences Summary

| Aspect | Business (XLS) | Consumer (CSV) |
|--------|----------------|----------------|
| Date format | DD-MM-YY | M/D/YYYY |
| Class column | Embedded in Product | Separate "Kl" column |
| Price columns | Excl/Incl VAT | Af/Bij (debit/credit) |
| Station names | Often abbreviated | Usually full names |
| File encoding | Windows-1252 | UTF-8 (may have encoding issues) |

### Special Record Types

| Product/Transaction | Description |
|---------------------|-------------|
| Treinreizer 1e/2e | Regular train journey (first/second class) |
| Correctieta | Correction/refund record (Business) |
| Reis | Regular journey (Consumer) |
| Studenten weekabonnement | Student weekly subscription |

### Data Processing Considerations

1. **Date Format**: Business uses DD-MM-YY, Consumer uses M/D/YYYY - detect and parse accordingly
2. **Time Format**: 24-hour format (HH:MM), no seconds
3. **Station Names**: Abbreviated Dutch names (e.g., "Den Haag", "Halfweg-Zw")
4. **Missing Check-outs**: "Reis zonder check-uit" indicates incomplete journey
5. **Encoding**: Files typically use Windows-1252 or UTF-8 encoding
6. **Price Format**: Euro symbol with comma as decimal separator (€ 14.97 or € 4,37)
7. **Correction Records**: Filter out "Correctieta" rows (refunds/corrections)
8. **Class Extraction**: Business: parse from "Product" column; Consumer: use "Kl" column
9. **Auto-detect Format**: Check for presence of "Dag" column (Business) or "Transactie" column (Consumer)

---

## Station Mapping Strategy

NS station names need to be mapped to Träwelling-compatible stations for check-in.

### Available Station Data

The project includes `data/stations.json` with 396 Dutch stations containing:

```json
{
  "code": "ASD",
  "name": "Amsterdam Centraal",
  "location": {
    "lat": 52.3788871765137,
    "lng": 4.90027761459351
  }
}
```

### Träwelling Station Lookup

Träwelling API supports multiple ways to find stations:

1. **By Coordinates** (Recommended): Use `GET /api/v1/station?latitude={lat}&longitude={lng}`
   - Best approach since we have lat/lng for all NS stations
   - Returns nearest Träwelling station with its internal ID

2. **By Name/Autocomplete**: Use `GET /api/v1/station/autocomplete/{query}`
   - Fuzzy search by station name
   - Returns list of matching stations

3. **By IBNR**: Direct lookup if IBNR code is known

### Station Mapping Approach

1. **Name Matching**: Match NS export station name to `data/stations.json` by name
2. **Coordinate Lookup**: Use matched station's lat/lng to query Träwelling API
3. **Cache Results**: Store Träwelling station IDs to avoid repeated API calls
4. **Fuzzy Matching**: Use fuzzy string matching for abbreviated station names

### Common Dutch Station Name Patterns

- "Amsterdam Centraal" → full name in stations.json
- "'s-Hertogenbosch" (note apostrophe)
- "Den Haag HS" vs "Den Haag Centraal"
- "Schiphol ✈" (with airplane emoji in some exports)
- "Halfweg-Zw" → "Halfweg-Zwanenburg" (abbreviated in NS exports)
- "Heemstede" → "Heemstede-Aerdenhout" (abbreviated in NS exports)
- "Haarlem" (may need disambiguation from Haarlem Spaarnwoude)

### Station Name Normalization

```python
def normalize_station_name(name: str) -> str:
    """Normalize station name for matching."""
    # Remove common suffixes/prefixes
    # Handle abbreviations
    # Strip whitespace and lowercase
    pass
```

---

## Development Guidelines

### Code Style

- Follow PEP 8 with `ruff` for enforcement
- Use type hints for all functions
- Docstrings in Google style format
- Maximum line length: 88 characters (Black default)

### Error Handling

```python
# Use custom exceptions
class RailSyncError(Exception):
    """Base exception for RailSync"""
    pass

class TraewellingAPIError(RailSyncError):
    """Träwelling API error"""
    pass

class ParseError(RailSyncError):
    """NS data parsing error"""
    pass
```

### Logging

- Use `structlog` for structured logging
- Log all API calls and responses (redact sensitive data)
- Include correlation IDs for request tracking

### Configuration

```python
# Use pydantic-settings for configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    traewelling_client_id: str
    traewelling_client_secret: str
    traewelling_redirect_uri: str = "http://localhost:8000/callback"
    traewelling_api_base: str = "https://traewelling.de/api/v1"
    
    class Config:
        env_file = ".env"
```

---

## Testing Instructions

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/railsync --cov-report=html

# Run specific test file
uv run pytest tests/test_parsers/test_csv_parser.py

# Run with verbose output
uv run pytest -v
```

### Test Categories

1. **Unit Tests**: Test individual functions and classes in isolation
2. **Integration Tests**: Test API client with mocked responses
3. **Parser Tests**: Test CSV/XLS parsing with sample files

### Test Data

- Store sample NS export files in `tests/fixtures/`
- Never commit real travel data; use anonymized samples
- Mock Träwelling API responses for deterministic tests

---

## Security Considerations

1. **Never commit credentials**: Use `.env` files and environment variables
2. **Token Storage**: Store OAuth tokens securely (consider keyring library)
3. **Input Validation**: Validate all parsed data before API submission
4. **Rate Limiting**: Respect Träwelling API rate limits
5. **Data Privacy**: Travel data is personal; handle with care

### Environment Variables

```bash
# .env.example
TRAEWELLING_CLIENT_ID=your_client_id
TRAEWELLING_CLIENT_SECRET=your_client_secret
TRAEWELLING_REDIRECT_URI=http://localhost:8000/callback
```

---

## Build & Run Commands

### Using uv (Recommended)

```bash
# Install uv (if not already installed)
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
uv pip install -e ".[dev]"

# Or use uv sync with pyproject.toml (creates venv automatically)
uv sync

# Run linting
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest

# Run the CLI
uv run python -m railsync import --file travel_data.csv

# Run development server (future web app)
uv run uvicorn railsync.web:app --reload
```

### Alternative: pip/Poetry

```bash
# Install dependencies with pip
pip install -e ".[dev]"

# Or with Poetry
poetry install
```

---

## Future: Azure Web App Deployment

When converting to a web application:

### Architecture

- **Frontend**: Simple HTML/CSS/JS or React SPA
- **Backend**: FastAPI with async endpoints
- **Authentication**: Azure AD B2C or direct OAuth flow
- **Storage**: Azure Blob Storage for temporary file uploads
- **Database**: Azure Cosmos DB or PostgreSQL for user settings

### Azure Resources Needed

- App Service Plan (B1 minimum for Python)
- App Service (Python 3.11)
- Application Insights for monitoring
- Key Vault for secrets
- Storage Account for file uploads

### CI/CD

Use GitHub Actions for:
1. Lint and test on PR
2. Build and deploy to staging on merge to `develop`
3. Deploy to production on release tag

---

## API Rate Limits & Best Practices

- Implement exponential backoff for retries
- Cache station lookups to minimize API calls
- Batch check-ins with appropriate delays
- Handle 429 (Too Many Requests) gracefully
- Log API response times for monitoring

---

## Troubleshooting

### Common Issues

1. **Station not found**: Check station name spelling, try autocomplete endpoint
2. **Trip not found**: The train/trip may not exist in Hafas data
3. **Authentication failed**: Verify OAuth tokens, check expiration
4. **Duplicate check-in**: Träwelling prevents duplicate check-ins; handle gracefully

### Debug Mode

```bash
# Enable debug logging (PowerShell)
$env:RAILSYNC_DEBUG = "true"
uv run python -m railsync import --file data.csv --verbose

# Enable debug logging (bash)
export RAILSYNC_DEBUG=true
uv run python -m railsync import --file data.csv --verbose
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass and linting is clean
5. Submit a Pull Request

### PR Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Type hints added
- [ ] Linting passes (`ruff check`)
- [ ] All tests pass (`pytest`)

---

## Documentation Requirements

**Important**: Documentation must be updated whenever code changes are made.

### When to Update Documentation

1. **New Features**: Add documentation for any new functionality
2. **API Changes**: Update API reference when endpoints or parameters change
3. **Configuration Changes**: Document new environment variables or settings
4. **Bug Fixes**: If the fix changes expected behavior, update relevant docs
5. **Refactoring**: Update code examples if function signatures change

### Documentation Locations

| Change Type | Update Location |
|-------------|-----------------|
| New module/class | Add docstrings + update README.md |
| CLI changes | Update README.md usage section |
| API client changes | Update this instruction file's API reference |
| Configuration | Update `.env.example` and README.md |
| New dependencies | Update `pyproject.toml` and document in README.md |

### Documentation Standards

```python
def parse_ns_export(file_path: Path, format_type: str = "auto") -> list[NSTrip]:
    """Parse NS travel data export file.
    
    Args:
        file_path: Path to the CSV or XLS export file.
        format_type: Export format - "business", "consumer", or "auto" for detection.
    
    Returns:
        List of NSTrip objects representing parsed journeys.
    
    Raises:
        ParseError: If the file format is invalid or unrecognized.
        FileNotFoundError: If the specified file does not exist.
    
    Example:
        >>> trips = parse_ns_export(Path("export.csv"))
        >>> print(f"Parsed {len(trips)} trips")
    """
```

### README.md Structure

The README.md should contain:
- Project description and badges
- Quick start / installation instructions
- Usage examples (CLI and programmatic)
- Configuration reference
- Troubleshooting section
- Contributing guidelines link

### Changelog

Maintain a `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description
```

---

## References

- [Träwelling](https://traewelling.de) - Main service
- [Träwelling API Docs](https://traewelling.de/api/documentation) - API documentation
- [Träwelling GitHub](https://github.com/Traewelling/traewelling) - Source code
- [Träwelling API Changelog](https://github.com/Traewelling/traewelling/blob/develop/API_CHANGELOG.md)
- [Mijn NS Zakelijk](https://www.ns.nl/zakelijk/mijn-ns-zakelijk) - NS Business portal
- [AGENTS.md Specification](https://agents.md/) - Agent instruction file format
