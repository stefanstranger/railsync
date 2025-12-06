"""RailSync CLI - Import NS travel data into Träwelling."""

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import structlog
import typer
from rich.console import Console
from rich.table import Table

from railsync import __version__
from railsync.config import Settings, get_settings
from railsync.models.ns_trip import NSExportFormat
from railsync.models.traewelling import BusinessType, Visibility
from railsync.parsers.base import detect_format, ParseError
from railsync.parsers.business_parser import BusinessParser
from railsync.parsers.consumer_parser import ConsumerParser
from railsync.services.checkin_service import CheckinService
from railsync.services.station_mapper import StationMapper
from railsync.services.traewelling_client import TraewellingClient, TraewellingAPIError

# Initialize
app = typer.Typer(
    name="railsync",
    help="Import NS travel data into Träwelling",
    no_args_is_help=True,
)
# Force UTF-8 output to avoid Windows encoding issues with spinner characters
console = Console(force_terminal=True, legacy_windows=False)


def setup_logging(debug: bool = False) -> None:
    """Configure structured logging.

    Args:
        debug: Enable debug level logging.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if not debug else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    import logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"RailSync version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """RailSync - Import NS travel data into Träwelling."""
    pass


@app.command()
def auth(
    client_id: Annotated[Optional[str], typer.Option(help="OAuth2 client ID")] = None,
    client_secret: Annotated[Optional[str], typer.Option(help="OAuth2 client secret")] = None,
) -> None:
    """Authenticate with Träwelling via OAuth2.

    Opens a browser window for authentication. The access token
    is saved for future use.
    """
    try:
        settings = get_settings()
    except Exception:
        if not client_id or not client_secret:
            console.print(
                "[red]Error:[/red] Missing credentials. Provide via --client-id/--client-secret "
                "or set TRAEWELLING_CLIENT_ID/TRAEWELLING_CLIENT_SECRET environment variables."
            )
            raise typer.Exit(1)
        settings = None

    cid = client_id or (settings.traewelling_client_id if settings else "")
    csecret = client_secret or (settings.traewelling_client_secret if settings else "")
    redirect_uri = settings.traewelling_redirect_uri if settings else "http://localhost:8000/callback"

    client = TraewellingClient(
        client_id=cid,
        client_secret=csecret,
        redirect_uri=redirect_uri,
    )

    console.print("[blue]Opening browser for Träwelling authentication...[/blue]")
    console.print("Please log in and authorize RailSync.\n")

    try:
        token = client.authenticate()
        console.print("[green]✓ Authentication successful![/green]\n")

        # Save token
        token_file = settings.token_file if settings else Path(".railsync_token")
        with open(token_file, "w") as f:
            json.dump({"access_token": token.access_token}, f)
        console.print(f"Token saved to: {token_file}")

        # Get user info
        user = client.get_user()
        console.print(f"\nLogged in as: [bold]{user.displayName}[/bold] (@{user.username})")
        console.print(f"Total distance: {user.totalDistance / 1000:.1f} km")
        console.print(f"Points: {user.points}")

    except TraewellingAPIError as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def parse(
    file: Annotated[Path, typer.Argument(help="NS export file (CSV or XLS)")],
    format: Annotated[
        Optional[str],
        typer.Option(help="Force format: 'business' or 'consumer'"),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output JSON file"),
    ] = None,
) -> None:
    """Parse NS export file and display trips.

    Reads a CSV or XLS file exported from NS and shows the parsed trips.
    """
    setup_logging()

    if not file.exists():
        console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(1)

    console.print(f"Parsing: [bold]{file}[/bold]\n")

    try:
        # Read file and detect format
        parser = BusinessParser()
        df = parser._read_file(file)

        # Determine format
        if format:
            detected_format = NSExportFormat(format)
        else:
            detected_format = detect_format(df)

        console.print(f"Detected format: [cyan]{detected_format.value}[/cyan]")

        # Parse with appropriate parser
        if detected_format == NSExportFormat.BUSINESS:
            parser = BusinessParser()
        elif detected_format == NSExportFormat.CONSUMER:
            parser = ConsumerParser()
        else:
            console.print("[red]Error:[/red] Unknown file format")
            raise typer.Exit(1)

        trips = parser.parse(file)
        console.print(f"Found [green]{len(trips)}[/green] trips\n")

        # Display trips table
        table = Table(title="Parsed Trips")
        table.add_column("Date", style="cyan")
        table.add_column("Time", style="cyan")
        table.add_column("From")
        table.add_column("To")
        table.add_column("Class")
        table.add_column("Complete", justify="center")

        for trip in trips[:20]:  # Show first 20
            table.add_row(
                trip.date.strftime("%Y-%m-%d"),
                trip.check_in_time.strftime("%H:%M"),
                trip.departure_station,
                trip.arrival_station or "-",
                str(trip.travel_class.value),
                "✓" if trip.is_complete else "✗",
            )

        console.print(table)

        if len(trips) > 20:
            console.print(f"\n... and {len(trips) - 20} more trips")

        # Output to JSON if requested
        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(
                    [trip.model_dump(mode="json") for trip in trips],
                    f,
                    indent=2,
                    default=str,
                )
            console.print(f"\nSaved to: {output}")

    except ParseError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="import")
def import_trips(
    file: Annotated[Path, typer.Argument(help="NS export file (CSV or XLS)")],
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Don't actually check in")] = False,
    visibility: Annotated[
        int,
        typer.Option("--visibility", "-V", help="Visibility (0=public, 1=unlisted, 2=followers, 3=private)"),
    ] = 0,
    message: Annotated[
        Optional[str],
        typer.Option("--message", "-m", help="Status message for check-ins"),
    ] = None,
    max_age: Annotated[
        int,
        typer.Option("--max-age", help="Maximum trip age in days"),
    ] = 7,
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug logging")] = False,
) -> None:
    """Import NS trips into Träwelling.

    Parses the NS export file and creates check-ins on Träwelling
    for each valid trip.
    """
    setup_logging(debug)

    if not file.exists():
        console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(1)

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        console.print("Run 'railsync auth' first or set environment variables.")
        raise typer.Exit(1)

    # Load token
    if not settings.token_file.exists():
        console.print("[red]Error:[/red] Not authenticated. Run 'railsync auth' first.")
        raise typer.Exit(1)

    with open(settings.token_file) as f:
        token_data = json.load(f)

    console.print(f"Importing from: [bold]{file}[/bold]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No check-ins will be created[/yellow]")
    console.print()

    # Initialize client and services
    client = TraewellingClient(
        client_id=settings.traewelling_client_id,
        client_secret=settings.traewelling_client_secret,
        redirect_uri=settings.traewelling_redirect_uri,
        api_base=settings.traewelling_api_base,
        access_token=token_data["access_token"],
    )

    station_mapper = StationMapper(
        client=client,
        stations_file=settings.stations_file,
        cache_file=settings.cache_file,
    )

    checkin_service = CheckinService(
        client=client,
        station_mapper=station_mapper,
        default_visibility=Visibility(visibility),
        default_business_type=BusinessType(settings.railsync_default_business_type),
        dry_run=dry_run,
    )

    try:
        # Parse file
        console.print("Parsing NS export...")

        parser = BusinessParser()
        df = parser._read_file(file)
        detected_format = detect_format(df)

        if detected_format == NSExportFormat.BUSINESS:
            parser = BusinessParser()
        else:
            parser = ConsumerParser()

        trips = parser.parse(file)

        console.print(f"Found [green]{len(trips)}[/green] trips")

        # Filter complete trips
        complete_trips = [t for t in trips if t.is_complete]
        console.print(f"Complete trips: [green]{len(complete_trips)}[/green]\n")

        if not complete_trips:
            console.print("[yellow]No complete trips to import.[/yellow]")
            raise typer.Exit(0)

        # Create check-ins
        console.print("Creating check-ins...")

        results = []
        for i, trip in enumerate(complete_trips, 1):
            console.print(f"  [{i}/{len(complete_trips)}] {trip.departure_station} -> {trip.arrival_station}")
            result = checkin_service.checkin_trip(trip, status_message=message)
            results.append(result)

        # Show results
        summary = checkin_service.get_summary(results)

        console.print("\n[bold]Results:[/bold]")
        console.print(f"  Successful: [green]{summary['successful']}[/green]")
        console.print(f"  Failed: [red]{summary['failed']}[/red]")
        console.print(f"  Skipped: [yellow]{summary['skipped']}[/yellow]")

        if summary['successful'] > 0:
            console.print(f"\n  Total points earned: [bold green]{summary['total_points']}[/bold green]")
            console.print(f"  Total distance: [bold]{summary['total_distance_km']:.1f}[/bold] km")

        if summary['errors']:
            console.print("\n[red]Errors:[/red]")
            for error in summary['errors'][:5]:
                console.print(f"  • {error}")

        # Save station cache
        station_mapper.save_cache()

    except TraewellingAPIError as e:
        console.print(f"[red]API error:[/red] {e}")
        raise typer.Exit(1)
    finally:
        client.close()


@app.command()
def stations(
    search: Annotated[Optional[str], typer.Argument(help="Station name to search")] = None,
    list_all: Annotated[bool, typer.Option("--list", "-l", help="List all stations")] = False,
) -> None:
    """Search or list NS stations.

    Uses the local stations.json database.
    """
    try:
        settings = get_settings()
        stations_file = settings.stations_file
    except Exception:
        stations_file = Path("data/stations.json")

    if not stations_file.exists():
        console.print(f"[red]Error:[/red] Stations file not found: {stations_file}")
        raise typer.Exit(1)

    with open(stations_file, encoding="utf-8") as f:
        stations_data = json.load(f)

    if search:
        # Search stations
        search_lower = search.lower()
        matches = [
            s for s in stations_data
            if search_lower in s["name"].lower() or search_lower in s["code"].lower()
        ]

        if not matches:
            console.print(f"No stations found matching: {search}")
            raise typer.Exit(0)

        table = Table(title=f"Stations matching '{search}'")
        table.add_column("Code", style="cyan")
        table.add_column("Name")
        table.add_column("Latitude")
        table.add_column("Longitude")

        for station in matches[:20]:
            table.add_row(
                station["code"],
                station["name"],
                f"{station['location']['lat']:.4f}",
                f"{station['location']['lng']:.4f}",
            )

        console.print(table)

        if len(matches) > 20:
            console.print(f"\n... and {len(matches) - 20} more")

    elif list_all:
        console.print(f"Total stations: [bold]{len(stations_data)}[/bold]")
    else:
        console.print("Use --list to show all stations or provide a search term.")


if __name__ == "__main__":
    app()
