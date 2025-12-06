"""Träwelling API client with OAuth2 authentication."""

import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import structlog

from railsync.models.traewelling import (
    CheckinRequest,
    CheckinResponse,
    DepartureInfo,
    TokenResponse,
    TraewellingStation,
    UserInfo,
)

logger = structlog.get_logger()


class TraewellingAPIError(Exception):
    """Error from Träwelling API."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class TraewellingClient:
    """Client for Träwelling API with OAuth2 authentication.

    Example:
        >>> client = TraewellingClient(
        ...     client_id="your_client_id",
        ...     client_secret="your_client_secret",
        ...     redirect_uri="http://localhost:8000/callback"
        ... )
        >>> client.authenticate()  # Opens browser for OAuth
        >>> user = client.get_user()
        >>> print(f"Logged in as {user.username}")
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8000/callback",
        api_base: str = "https://traewelling.de/api/v1",
        access_token: str | None = None,
    ):
        """Initialize the Träwelling client.

        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            redirect_uri: OAuth2 redirect URI.
            api_base: Base URL for the API.
            access_token: Existing access token (optional).
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.api_base = api_base.rstrip("/")
        self.access_token = access_token

        self._client = httpx.Client(
            base_url=self.api_base,
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _get_headers(self) -> dict[str, str]:
        """Get headers with authorization."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            method: HTTP method.
            endpoint: API endpoint.
            **kwargs: Additional request arguments.

        Returns:
            JSON response data.

        Raises:
            TraewellingAPIError: If request fails.
        """
        headers = self._get_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        try:
            response = self._client.request(
                method,
                endpoint,
                headers=headers,
                **kwargs,
            )

            if response.status_code == 429:
                raise TraewellingAPIError(
                    "Rate limit exceeded. Please wait before retrying.",
                    status_code=429,
                )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {"error": response.text}

                raise TraewellingAPIError(
                    f"API error: {response.status_code}",
                    status_code=response.status_code,
                    response=error_data,
                )

            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.RequestError as e:
            raise TraewellingAPIError(f"Request failed: {e}") from e

    # ==================== Authentication ====================

    def get_authorization_url(self, state: str = "railsync") -> str:
        """Get the OAuth2 authorization URL.

        Args:
            state: State parameter for CSRF protection.

        Returns:
            Authorization URL to redirect user to.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "read-statuses write-statuses read-notifications",
            "state": state,
        }
        return f"https://traewelling.de/oauth/authorize?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback.

        Returns:
            Token response with access token.
        """
        response = self._client.post(
            "https://traewelling.de/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )

        if response.status_code != 200:
            raise TraewellingAPIError(
                f"Token exchange failed: {response.text}",
                status_code=response.status_code,
            )

        data = response.json()
        self.access_token = data["access_token"]
        return TokenResponse(**data)

    def authenticate(self) -> TokenResponse:
        """Perform OAuth2 authentication flow.

        Opens browser for user authorization and starts local server
        to receive the callback.

        Returns:
            Token response with access token.
        """
        auth_code: str | None = None

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                nonlocal auth_code
                query = parse_qs(urlparse(self.path).query)
                if "code" in query:
                    auth_code = query["code"][0]
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body><h1>Authentication successful!</h1>"
                        b"<p>You can close this window.</p></body></html>"
                    )
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Authorization failed")

            def log_message(self, format: str, *args: Any) -> None:
                pass  # Suppress server logs

        # Parse redirect URI to get host and port
        parsed = urlparse(self.redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000

        # Start callback server
        server = HTTPServer((host, port), CallbackHandler)
        server.timeout = 120  # 2 minute timeout

        # Open browser
        auth_url = self.get_authorization_url()
        logger.info("Opening browser for authentication", url=auth_url)
        webbrowser.open(auth_url)

        # Wait for callback
        logger.info("Waiting for authorization callback...")
        server.handle_request()
        server.server_close()

        if not auth_code:
            raise TraewellingAPIError("Authorization failed: no code received")

        return self.exchange_code(auth_code)

    # ==================== User ====================

    def get_user(self) -> UserInfo:
        """Get current authenticated user info.

        Returns:
            User information.
        """
        data = self._request("GET", "/auth/user")
        return UserInfo(**data["data"])

    # ==================== Stations ====================

    def search_station_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        radius: float = 0.01,
    ) -> TraewellingStation | None:
        """Search for station by coordinates using bounding box.

        Args:
            latitude: Latitude.
            longitude: Longitude.
            radius: Bounding box radius in degrees (default ~1km).

        Returns:
            Nearest station or None.
        """
        try:
            # Use bounding box parameters as required by the API
            data = self._request(
                "GET",
                "/station",
                params={
                    "min_lat": latitude - radius,
                    "max_lat": latitude + radius,
                    "min_lon": longitude - radius,
                    "max_lon": longitude + radius,
                },
            )
            stations = data.get("data", [])
            if stations:
                # Return the first/closest station
                return TraewellingStation(**stations[0])
            return None
        except TraewellingAPIError as e:
            logger.warning("Station search failed", error=str(e))
            return None

    def search_station_by_name(self, query: str) -> list[TraewellingStation]:
        """Search for stations by name.

        Args:
            query: Search query.

        Returns:
            List of matching stations.
        """
        data = self._request("GET", f"/trains/station/autocomplete/{query}")
        return [TraewellingStation(**s) for s in data.get("data", [])]

    def get_departures(
        self,
        station_id: int,
        when: datetime | None = None,
    ) -> list[DepartureInfo]:
        """Get departures from a station.

        Args:
            station_id: Träwelling station ID.
            when: Optional datetime for departure time.

        Returns:
            List of departures.
        """
        params: dict[str, Any] = {}
        if when:
            params["when"] = when.isoformat()

        data = self._request("GET", f"/station/{station_id}/departures", params=params)
        return [DepartureInfo(**d) for d in data.get("data", [])]

    # ==================== Check-in ====================

    def checkin(self, request: CheckinRequest) -> CheckinResponse:
        """Create a check-in.

        Args:
            request: Check-in request data.

        Returns:
            Check-in response with status info.
        """
        data = self._request(
            "POST",
            "/trains/checkin",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        return CheckinResponse(**data["data"])

    def get_active_status(self) -> dict[str, Any] | None:
        """Get current active status (if any).

        Returns:
            Active status data or None.
        """
        try:
            data = self._request("GET", "/user/statuses/active")
            if data.get("data"):
                return data["data"]
            return None
        except TraewellingAPIError:
            return None

    # ==================== Context Manager ====================

    def __enter__(self) -> "TraewellingClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self._client.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
