# RailSync 🚂

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Automate your NS train journey check-ins on [Träwelling](https://traewelling.de) with ease!

RailSync imports travel data from Nederlandse Spoorwegen (CSV/XLS exports) and uses the Träwelling API to create check-ins, helping you earn points and share your journeys effortlessly.

## ✨ Features

- 📥 **Import NS travel data** from both business (XLS) and consumer (CSV) exports
- 🚉 **Automatic station mapping** using coordinates from 396 Dutch stations
- 🔐 **OAuth2 authentication** with Träwelling
- 📊 **Dry-run mode** to preview check-ins before creating them
- 🎯 **Fuzzy station matching** for abbreviated station names
- 💾 **Station caching** to minimize API calls

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- A [Träwelling](https://traewelling.de) account
- NS travel export file (CSV or XLS)

### Installation

```bash
# Clone the repository
git clone https://github.com/stefanstranger/railsync.git
cd railsync

# Install with uv
uv sync

# Or with pip
pip install -e .
```

### Configuration

1. **Create a Träwelling OAuth application** at https://traewelling.de/settings/applications
   - Set redirect URI to `http://localhost:8000/callback`

2. **Create a `.env` file** (or copy from `.env.example`):

```bash
cp .env.example .env
```

3. **Edit `.env`** with your credentials:

```env
TRAEWELLING_CLIENT_ID=your_client_id
TRAEWELLING_CLIENT_SECRET=your_client_secret
```

### Usage

#### 1. Authenticate with Träwelling

```bash
uv run railsync auth
```

This opens your browser to log in and authorize RailSync.

#### 2. Parse and preview your NS export

```bash
# Preview trips from your NS export
uv run railsync parse your_ns_export.csv

# Save parsed trips to JSON
uv run railsync parse your_ns_export.csv --output trips.json
```

#### 3. Import trips to Träwelling

```bash
# Dry run (preview without creating check-ins)
uv run railsync import your_ns_export.csv --dry-run

# Actually create check-ins
uv run railsync import your_ns_export.csv

# With custom visibility (0=public, 1=unlisted, 2=followers, 3=private)
uv run railsync import your_ns_export.csv --visibility 1

# With a status message
uv run railsync import your_ns_export.csv --message "Imported from NS"
```

#### 4. Search stations

```bash
# Search for a station
uv run railsync stations Amsterdam

# List all stations
uv run railsync stations --list
```

## 📁 Supported NS Export Formats

### Business Export (XLS) - Mijn NS Zakelijk

Export from [Mijn NS Zakelijk](https://www.ns.nl/zakelijk/mijn-ns-zakelijk/reizen-en-transacties) with columns like:
- Dag, Datum, Product, Check in, Vertrek, Check uit, Bestemming, etc.

### Consumer Export (CSV) - NS App

Export from the NS app/website with columns like:
- Datum, Check in, Vertrek, Check uit, Bestemming, Transactie, Kl, Product, etc.

RailSync automatically detects the format.

## 🛠️ Development

### Setup

```bash
# Install with dev dependencies
uv sync

# Run linting
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/railsync --cov-report=html
```

### Project Structure

```
railsync/
├── src/railsync/
│   ├── models/          # Data models (NSTrip, Träwelling)
│   ├── parsers/         # CSV/XLS parsers
│   ├── services/        # Business logic services
│   ├── config.py        # Configuration management
│   └── main.py          # CLI entry point
├── tests/               # Test files
├── data/
│   └── stations.json    # NS station database
└── pyproject.toml       # Project configuration
```

## 🔧 CLI Commands

| Command | Description |
|---------|-------------|
| `railsync auth` | Authenticate with Träwelling |
| `railsync parse <file>` | Parse NS export and show trips |
| `railsync import <file>` | Import trips to Träwelling |
| `railsync stations [search]` | Search station database |

### Import Options

| Option | Description |
|--------|-------------|
| `--dry-run, -n` | Preview without creating check-ins |
| `--visibility, -V` | Set visibility (0-3) |
| `--message, -m` | Add status message |
| `--max-age` | Maximum trip age in days (default: 7) |
| `--debug` | Enable debug logging |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure tests pass (`uv run pytest`)
5. Ensure linting passes (`uv run ruff check`)
6. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Träwelling](https://traewelling.de) for the amazing train tracking service
- [NS](https://www.ns.nl) for providing travel data exports
- The open-source community for the excellent tools used in this project

## 📚 References

- [Träwelling API Documentation](https://traewelling.de/api/documentation)
- [NS Zakelijk Portal](https://www.ns.nl/zakelijk/mijn-ns-zakelijk)
- [agents.md Specification](https://agents.md/)
