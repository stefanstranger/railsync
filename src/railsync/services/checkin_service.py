"""Check-in service for creating Träwelling check-ins from NS trips."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from railsync.models.ns_trip import NSTrip, TripType
from railsync.models.traewelling import (
    BusinessType,
    CheckinRequest,
    CheckinResponse,
    DepartureInfo,
    Visibility,
)
from railsync.services.station_mapper import StationMapper
from railsync.services.traewelling_client import TraewellingAPIError, TraewellingClient

logger = structlog.get_logger()


class CheckinError(Exception):
    """Error during check-in process."""

    pass


class CheckinResult:
    """Result of a check-in attempt."""

    def __init__(
        self,
        trip: NSTrip,
        success: bool,
        response: CheckinResponse | None = None,
        error: str | None = None,
        skipped: bool = False,
        skip_reason: str | None = None,
    ):
        self.trip = trip
        self.success = success
        self.response = response
        self.error = error
        self.skipped = skipped
        self.skip_reason = skip_reason

    @property
    def points(self) -> int:
        """Get points earned from check-in."""
        return self.response.points if self.response else 0


class CheckinService:
    """Service for creating Träwelling check-ins from NS trips.

    Handles the full flow of:
    1. Mapping NS stations to Träwelling stations
    2. Finding matching departures/trips
    3. Creating check-ins via the API

    Example:
        >>> service = CheckinService(client, station_mapper)
        >>> results = service.checkin_trips(trips)
        >>> for result in results:
        ...     if result.success:
        ...         print(f"Checked in! Earned {result.points} points")
    """

    def __init__(
        self,
        client: TraewellingClient,
        station_mapper: StationMapper,
        default_visibility: Visibility = Visibility.PUBLIC,
        default_business_type: BusinessType = BusinessType.PRIVATE,
        dry_run: bool = False,
    ):
        """Initialize the check-in service.

        Args:
            client: Träwelling API client.
            station_mapper: Station mapping service.
            default_visibility: Default visibility for check-ins.
            default_business_type: Default business type for check-ins.
            dry_run: If True, don't actually create check-ins.
        """
        self.client = client
        self.station_mapper = station_mapper
        self.default_visibility = default_visibility
        self.default_business_type = default_business_type
        self.dry_run = dry_run

    def _trip_type_to_business(self, trip_type: TripType) -> BusinessType:
        """Convert NS trip type to Träwelling business type.

        Args:
            trip_type: NS trip type.

        Returns:
            Corresponding Träwelling business type.
        """
        mapping = {
            TripType.PRIVATE: BusinessType.PRIVATE,
            TripType.BUSINESS: BusinessType.BUSINESS,
            TripType.COMMUTE: BusinessType.COMMUTE,
        }
        return mapping.get(trip_type, self.default_business_type)

    def _find_matching_departure(
        self,
        station_id: int,
        departure_time: datetime,
        destination_name: str,
        tolerance_minutes: int = 30,
    ) -> DepartureInfo | None:
        """Find a matching departure from Träwelling.

        Args:
            station_id: Träwelling station ID.
            departure_time: Expected departure time.
            destination_name: Destination station name.
            tolerance_minutes: Time tolerance for matching.

        Returns:
            Matching departure or None.
        """
        try:
            departures = self.client.get_departures(station_id, when=departure_time)
        except TraewellingAPIError as e:
            logger.warning("Failed to get departures", error=str(e))
            return None

        # Find best matching departure
        tolerance = timedelta(minutes=tolerance_minutes)
        best_match: DepartureInfo | None = None
        best_score = 0.0

        for dep in departures:
            # Check time tolerance
            time_diff = abs((dep.plannedDeparture - departure_time).total_seconds())
            if time_diff > tolerance.total_seconds():
                continue

            # Check destination match (simple substring matching)
            dest_lower = destination_name.lower()
            direction_lower = dep.direction.lower()

            if dest_lower in direction_lower or direction_lower in dest_lower:
                # Score based on time proximity (closer = better)
                score = 1.0 - (time_diff / tolerance.total_seconds())
                if score > best_score:
                    best_score = score
                    best_match = dep

        return best_match

    def checkin_trip(
        self,
        trip: NSTrip,
        status_message: str | None = None,
        visibility: Visibility | None = None,
    ) -> CheckinResult:
        """Create a check-in for a single NS trip.

        Args:
            trip: NS trip to check in.
            status_message: Optional status message.
            visibility: Optional visibility override.

        Returns:
            CheckinResult with success/failure info.
        """
        # Validate trip
        if not trip.is_complete:
            return CheckinResult(
                trip=trip,
                success=False,
                skipped=True,
                skip_reason="Incomplete trip (missing check-out)",
            )

        if not trip.arrival_station:
            return CheckinResult(
                trip=trip,
                success=False,
                skipped=True,
                skip_reason="Missing arrival station",
            )

        # Map stations
        departure_station, arrival_station = self.station_mapper.get_station_pair(
            trip.departure_station,
            trip.arrival_station,
        )

        if not departure_station:
            return CheckinResult(
                trip=trip,
                success=False,
                error=f"Could not find departure station: {trip.departure_station}",
            )

        if not arrival_station:
            return CheckinResult(
                trip=trip,
                success=False,
                error=f"Could not find arrival station: {trip.arrival_station}",
            )

        # Find matching departure
        matching_departure = self._find_matching_departure(
            station_id=departure_station.id,
            departure_time=trip.check_in_time,
            destination_name=trip.arrival_station,
        )

        if not matching_departure:
            return CheckinResult(
                trip=trip,
                success=False,
                error=f"No matching train found at {trip.check_in_time.strftime('%H:%M')}",
            )

        # Build check-in request
        request = CheckinRequest(
            tripId=matching_departure.tripId,
            lineName=matching_departure.lineName,
            start=departure_station.id,
            destination=arrival_station.id,
            departure=trip.check_in_time,
            arrival=trip.check_out_time,
            body=status_message,
            business=self._trip_type_to_business(trip.trip_type),
            visibility=visibility or self.default_visibility,
            ibnr=False,  # Using Träwelling station IDs, not IBNR
        )

        logger.info(
            "Creating check-in",
            departure=trip.departure_station,
            arrival=trip.arrival_station,
            time=trip.check_in_time.strftime("%Y-%m-%d %H:%M"),
            line=matching_departure.lineName,
            dry_run=self.dry_run,
        )

        if self.dry_run:
            return CheckinResult(
                trip=trip,
                success=True,
                skipped=True,
                skip_reason="Dry run mode",
            )

        # Create check-in
        try:
            response = self.client.checkin(request)
            logger.info(
                "Check-in successful",
                status_id=response.id,
                points=response.points,
                distance=response.distance,
            )
            return CheckinResult(trip=trip, success=True, response=response)
        except TraewellingAPIError as e:
            logger.error("Check-in failed", error=str(e))
            return CheckinResult(trip=trip, success=False, error=str(e))

    def checkin_trips(
        self,
        trips: list[NSTrip],
        status_message: str | None = None,
        visibility: Visibility | None = None,
        skip_past_trips: bool = True,
        max_age_days: int = 7,
    ) -> list[CheckinResult]:
        """Create check-ins for multiple NS trips.

        Args:
            trips: List of NS trips to check in.
            status_message: Optional status message for all check-ins.
            visibility: Optional visibility override.
            skip_past_trips: Whether to skip trips older than max_age_days.
            max_age_days: Maximum age of trips to check in.

        Returns:
            List of CheckinResult objects.
        """
        results: list[CheckinResult] = []
        now = datetime.now()
        cutoff = now - timedelta(days=max_age_days)

        # Sort trips by date (oldest first)
        sorted_trips = sorted(trips, key=lambda t: t.check_in_time)

        for trip in sorted_trips:
            # Skip old trips
            if skip_past_trips and trip.check_in_time < cutoff:
                results.append(
                    CheckinResult(
                        trip=trip,
                        success=False,
                        skipped=True,
                        skip_reason=f"Trip older than {max_age_days} days",
                    )
                )
                continue

            # Skip future trips
            if trip.check_in_time > now:
                results.append(
                    CheckinResult(
                        trip=trip,
                        success=False,
                        skipped=True,
                        skip_reason="Future trip",
                    )
                )
                continue

            result = self.checkin_trip(trip, status_message, visibility)
            results.append(result)

        return results

    def get_summary(self, results: list[CheckinResult]) -> dict[str, Any]:
        """Get summary statistics for check-in results.

        Args:
            results: List of check-in results.

        Returns:
            Summary dictionary.
        """
        successful = [r for r in results if r.success and not r.skipped]
        failed = [r for r in results if not r.success and not r.skipped]
        skipped = [r for r in results if r.skipped]

        total_points = sum(r.points for r in successful)
        total_distance = sum(r.response.distance for r in successful if r.response)

        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "skipped": len(skipped),
            "total_points": total_points,
            "total_distance_km": total_distance / 1000,
            "errors": [r.error for r in failed if r.error],
            "skip_reasons": [r.skip_reason for r in skipped if r.skip_reason],
        }
