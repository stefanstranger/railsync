"""Parser for NS Consumer export (CSV from NS App/Website)."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
import structlog

from railsync.models.ns_trip import NSExportFormat, NSTrip, TravelClass, TripType
from railsync.parsers.base import BaseParser, ParseError

logger = structlog.get_logger()


class ConsumerParser(BaseParser):
    """Parser for NS Consumer CSV exports from NS App/Website.

    Expected columns:
    - Datum: Date (M/D/YYYY format)
    - Check in: Check-in time (HH:MM)
    - Vertrek: Departure station
    - Check uit: Check-out time (HH:MM)
    - Bestemming: Destination station
    - Af: Amount deducted
    - Bij: Amount added
    - Transactie: Transaction type (e.g., "Reis")
    - Kl: Travel class (1 or 2)
    - Product: Product/subscription name
    - Prive/Zakelijk: Private/Business indicator
    - Opmerking: Remarks
    """

    def can_parse(self, df: pd.DataFrame) -> bool:
        """Check if dataframe matches consumer format.

        Args:
            df: DataFrame to check.

        Returns:
            True if this is a consumer format export.
        """
        columns_lower = set(df.columns.str.lower())
        # Consumer format has "Transactie" and "Kl" columns
        return "transactie" in columns_lower or (
            "kl" in columns_lower and "af" in columns_lower
        )

    def parse(self, file_path: Path) -> list[NSTrip]:
        """Parse NS Consumer CSV export file.

        Args:
            file_path: Path to the CSV file.

        Returns:
            List of NSTrip objects.

        Raises:
            ParseError: If parsing fails.
        """
        df = self._read_file(file_path)

        if not self.can_parse(df):
            raise ParseError("File does not appear to be a consumer format export")

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
            "Parsed consumer export",
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
        # Only process "Reis" transactions
        transactie = self._get_value(row, "transactie", "")
        if transactie and transactie.lower() != "reis":
            logger.debug("Skipping non-reis transaction", row=idx, transactie=transactie)
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

        # Parse travel class
        travel_class = self._parse_class(row)

        # Parse trip type
        trip_type = self._parse_trip_type(row)

        # Parse price (from "Af" column)
        price = self._parse_price(row)

        # Get product name
        product = self._get_value(row, "product", "Unknown")

        return NSTrip(
            date=check_in_time,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            departure_station=departure,
            arrival_station=destination if destination else None,
            travel_class=travel_class,
            product=product or "Unknown",
            trip_type=trip_type,
            price=price,
            description=self._get_value(row, "opmerking", None),
            card_number=None,  # Consumer format doesn't have card number
            is_complete=is_complete,
            source_format=NSExportFormat.CONSUMER,
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
            if col.lower() == col_name.lower():
                val = row[col]
                if pd.isna(val):
                    return default
                return str(val).strip()
        return default

    def _parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """Parse date and time strings into datetime.

        Args:
            date_str: Date string (M/D/YYYY format).
            time_str: Time string (HH:MM format).

        Returns:
            Combined datetime.

        Raises:
            ValueError: If parsing fails.
        """
        if not date_str or not time_str:
            raise ValueError("Missing date or time")

        # Handle M/D/YYYY format (US format used in consumer export)
        try:
            date_part = datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            # Try other formats
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                try:
                    date_part = datetime.strptime(date_str, fmt).date()
                    break
                except ValueError:
                    continue
            else:
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
        # Consumer format has dedicated "Kl" column
        kl = self._get_value(row, "kl", "")
        if kl:
            if "1" in str(kl):
                return TravelClass.FIRST
            return TravelClass.SECOND

        return TravelClass.SECOND

    def _parse_trip_type(self, row: pd.Series) -> TripType:
        """Parse trip type from row.

        Args:
            row: DataFrame row.

        Returns:
            TripType enum value.
        """
        value = self._get_value(row, "prive/zakelijk", "")
        value_lower = value.lower() if value else ""

        if "zakelijk" in value_lower or "business" in value_lower:
            return TripType.BUSINESS
        elif "woon-werk" in value_lower or "commute" in value_lower:
            return TripType.COMMUTE

        return TripType.PRIVATE

    def _parse_price(self, row: pd.Series) -> Decimal | None:
        """Parse price from "Af" column.

        Args:
            row: DataFrame row.

        Returns:
            Price as Decimal or None.
        """
        price_str = self._get_value(row, "af", None)

        if not price_str:
            return None

        try:
            # Remove currency symbol and whitespace
            price_str = price_str.replace("€", "").replace(" ", "").strip()
            # Handle both comma and dot as decimal separator
            price_str = price_str.replace(",", ".")
            # Handle special characters (encoding issues)
            price_str = price_str.replace("¬", "").replace("â", "")
            return Decimal(price_str)
        except (InvalidOperation, ValueError):
            return None
