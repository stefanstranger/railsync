"""Parser for NS Business export (XLS from Mijn NS Zakelijk)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import structlog

from railsync.models.ns_trip import NSExportFormat, NSTrip, TravelClass, TripType
from railsync.parsers.base import BaseParser, ParseError

logger = structlog.get_logger()


class BusinessParser(BaseParser):
    """Parser for NS Business XLS exports from Mijn NS Zakelijk.

    Expected columns:
    - Dag: Day of week (ma, di, wo, etc.)
    - Datum: Date (DD-MM-YY)
    - Product: Product name with class (e.g., "Treinreizer 1e")
    - klasse: Travel class
    - Check in: Check-in time (HH:MM)
    - Vertrek: Departure station
    - Check uit: Check-out time (HH:MM)
    - Bestemming: Destination station
    - Omschrijving: Description
    - Prijs (excl.: Price excluding VAT
    - Prive/Zakelijk: Private/Business indicator
    - Kaartnummer: Card number
    """

    # Column name mappings (lowercase for matching)
    COLUMN_MAP = {
        "datum": "date",
        "check in": "check_in_time",
        "vertrek": "departure",
        "check uit": "check_out_time",
        "bestemming": "destination",
        "product": "product",
        "klasse": "class",
        "omschrijving": "description",
        "prijs (excl.": "price",
        "prive/zakelijk": "trip_type",
        "kaartnummer": "card_number",
    }

    def can_parse(self, df: pd.DataFrame) -> bool:
        """Check if dataframe matches business format.

        Args:
            df: DataFrame to check.

        Returns:
            True if this is a business format export.
        """
        columns_lower = set(df.columns.str.lower())
        # Check for distinctive business format columns
        return "dag" in columns_lower or (
            "gefactureerd" in columns_lower and "kaarthouder" in columns_lower
        )

    def parse(self, file_path: Path) -> list[NSTrip]:
        """Parse NS Business XLS export file.

        Args:
            file_path: Path to the XLS file.

        Returns:
            List of NSTrip objects.

        Raises:
            ParseError: If parsing fails.
        """
        df = self._read_file(file_path)

        if not self.can_parse(df):
            raise ParseError("File does not appear to be a business format export")

        trips: list[NSTrip] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            try:
                trip = self._parse_row(row, idx)
                if trip is not None:
                    trips.append(trip)
            except Exception as e:
                errors.append(f"Row {idx}: {e}")
                logger.warning("Failed to parse row", row=idx, error=str(e))

        logger.info(
            "Parsed business export",
            total_rows=len(df),
            valid_trips=len(trips),
            errors=len(errors),
        )

        if errors and not trips:
            raise ParseError(f"No valid trips found. Errors: {errors[:5]}")

        return trips

    def _parse_row(self, row: pd.Series, idx: int) -> NSTrip | None:
        """Parse a single row into an NSTrip.

        Args:
            row: DataFrame row.
            idx: Row index for logging.

        Returns:
            NSTrip object or None if row should be skipped.
        """
        # Skip correction rows
        product = self._get_value(row, "product", "")
        if "correctie" in product.lower():
            logger.debug("Skipping correction row", row=idx)
            return None

        # Skip rows without departure station
        departure = self._get_value(row, "vertrek", "")
        if not departure:
            logger.debug("Skipping row without departure", row=idx)
            return None

        # Parse date and times
        date_str = self._get_value(row, "datum", "")
        check_in_str = self._get_value(row, "check in", "")
        check_out_str = self._get_value(row, "check uit", "")

        check_in_time = self._parse_datetime(date_str, check_in_str)
        check_out_time = self._parse_datetime(date_str, check_out_str) if check_out_str else None

        # Determine if trip is complete
        destination = self._get_value(row, "bestemming", "")
        is_complete = bool(destination and check_out_time)

        # Parse travel class from product or klasse column
        travel_class = self._parse_class(row)

        # Parse trip type
        trip_type = self._parse_trip_type(row)

        # Parse price
        price = self._parse_price(row)

        return NSTrip(
            date=check_in_time,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            departure_station=departure,
            arrival_station=destination if destination else None,
            travel_class=travel_class,
            product=product,
            trip_type=trip_type,
            price=price,
            description=self._get_value(row, "omschrijving", None),
            card_number=self._get_value(row, "kaartnummer", None),
            is_complete=is_complete,
            source_format=NSExportFormat.BUSINESS,
        )

    def _get_value(self, row: pd.Series, col_name: str, default: str | None) -> str | None:
        """Get value from row by column name (case-insensitive).

        Args:
            row: DataFrame row.
            col_name: Column name to look for.
            default: Default value if not found.

        Returns:
            Column value or default.
        """
        for col in row.index:
            if col.lower().startswith(col_name.lower()):
                val = row[col]
                if pd.isna(val):
                    return default
                return str(val).strip()
        return default

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse date and time strings into datetime.

        Args:
            date_str: Date string (DD-MM-YY format).
            time_str: Time string (HH:MM format).

        Returns:
            Combined datetime.

        Raises:
            ValueError: If parsing fails.
        """
        if not date_str or not time_str:
            raise ValueError("Missing date or time")

        # Handle DD-MM-YY format
        try:
            # Try DD-MM-YY first
            date_part = datetime.strptime(date_str, "%d-%m-%y").date()
        except ValueError:
            # Try DD-MM-YYYY
            try:
                date_part = datetime.strptime(date_str, "%d-%m-%Y").date()
            except ValueError:
                raise ValueError(f"Cannot parse date: {date_str}")

        # Parse time (HH:MM)
        try:
            time_part = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            raise ValueError(f"Cannot parse time: {time_str}")

        return datetime.combine(date_part, time_part)

    def _parse_class(self, row: pd.Series) -> TravelClass:
        """Parse travel class from row.

        Args:
            row: DataFrame row.

        Returns:
            TravelClass enum value.
        """
        # Try klasse column first
        klasse = self._get_value(row, "klasse", "")
        if klasse:
            if "1" in klasse:
                return TravelClass.FIRST
            return TravelClass.SECOND

        # Try to extract from product
        product = self._get_value(row, "product", "")
        if "1e" in product.lower() or "eerste" in product.lower():
            return TravelClass.FIRST

        return TravelClass.SECOND

    def _parse_trip_type(self, row: pd.Series) -> TripType:
        """Parse trip type from row.

        Args:
            row: DataFrame row.

        Returns:
            TripType enum value.
        """
        value = self._get_value(row, "prive/zakelijk", "")
        if not value:
            # Check kenmerk column as fallback
            value = self._get_value(row, "kenmerk", "")

        value_lower = value.lower() if value else ""

        if "zakelijk" in value_lower or "business" in value_lower:
            return TripType.BUSINESS
        elif "woon-werk" in value_lower or "commute" in value_lower:
            return TripType.COMMUTE

        return TripType.PRIVATE

    def _parse_price(self, row: pd.Series) -> Decimal | None:
        """Parse price from row.

        Args:
            row: DataFrame row.

        Returns:
            Price as Decimal or None.
        """
        price_str = self._get_value(row, "prijs (excl.", None)
        if not price_str:
            price_str = self._get_value(row, "prijs", None)

        if not price_str:
            return None

        try:
            # Remove currency symbol and whitespace
            price_str = price_str.replace("€", "").replace(" ", "").strip()
            # Handle both comma and dot as decimal separator
            price_str = price_str.replace(",", ".")
            return Decimal(price_str)
        except (InvalidOperation, ValueError):
            return None
