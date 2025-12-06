"""Base parser and format detection for NS exports."""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd
import structlog

from railsync.models.ns_trip import NSExportFormat, NSTrip

logger = structlog.get_logger()


class ParseError(Exception):
    """Error during parsing of NS export data."""

    pass


class BaseParser(ABC):
    """Base class for NS export parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> list[NSTrip]:
        """Parse the NS export file and return list of trips.

        Args:
            file_path: Path to the NS export file.

        Returns:
            List of NSTrip objects.

        Raises:
            ParseError: If parsing fails.
        """
        pass

    @abstractmethod
    def can_parse(self, df: pd.DataFrame) -> bool:
        """Check if this parser can handle the given dataframe.

        Args:
            df: DataFrame loaded from the file.

        Returns:
            True if this parser can handle the data.
        """
        pass

    def _read_file(self, file_path: Path) -> pd.DataFrame:
        """Read file into DataFrame based on extension.

        Args:
            file_path: Path to the file.

        Returns:
            DataFrame with file contents.

        Raises:
            ParseError: If file cannot be read.
        """
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".csv":
                # Try different encodings
                for encoding in ["utf-8", "windows-1252", "latin-1"]:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=None, engine="python")
                        logger.debug("Read CSV file", encoding=encoding, rows=len(df))
                        return df
                    except UnicodeDecodeError:
                        continue
                raise ParseError(f"Could not decode CSV file: {file_path}")

            elif suffix in [".xls", ".xlsx"]:
                # Use xlrd for old .xls (Excel 97-2003), openpyxl for .xlsx
                engine = "xlrd" if suffix == ".xls" else "openpyxl"
                df = pd.read_excel(file_path, engine=engine)
                logger.debug("Read Excel file", engine=engine, rows=len(df))
                return df

            else:
                raise ParseError(f"Unsupported file format: {suffix}")

        except Exception as e:
            if isinstance(e, ParseError):
                raise
            raise ParseError(f"Failed to read file {file_path}: {e}") from e


def detect_format(df: pd.DataFrame) -> NSExportFormat:
    """Detect the format of an NS export based on columns.

    Args:
        df: DataFrame loaded from the file.

    Returns:
        Detected export format.
    """
    columns = set(df.columns.str.lower())

    # Business format has "Dag" column
    if "dag" in columns:
        return NSExportFormat.BUSINESS

    # Consumer format has "Transactie" column
    if "transactie" in columns:
        return NSExportFormat.CONSUMER

    # Fallback: check for other distinctive columns
    if "kaartnummer" in columns and "gefactureerd" in columns:
        return NSExportFormat.BUSINESS

    if "kl" in columns and "af" in columns:
        return NSExportFormat.CONSUMER

    return NSExportFormat.UNKNOWN
