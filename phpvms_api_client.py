"""
phpVMS API Client

A comprehensive Python client for the phpVMS API.
This client provides access to all phpVMS API endpoints for flight simulation management.

Author: Generated for phpVMS API
Version: 1.0.0
"""

import requests
import json
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class PirepState(Enum):
    """PIREP States"""
    DRAFT = 0
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3
    CANCELLED = 4


class PirepSource(Enum):
    """PIREP Sources"""
    MANUAL = 0
    ACARS = 1


class AcarsType(Enum):
    """ACARS Types"""
    FLIGHT_PATH = 1
    LOG = 2
    ROUTE = 3


class AircraftState(Enum):
    """Aircraft States"""
    PARKED = 0
    IN_USE = 1
    IN_AIR = 2


class AircraftStatus(Enum):
    """Aircraft Status"""
    ACTIVE = 1
    MAINTENANCE = 2
    RETIRED = 3


@dataclass
class User:
    """User/Pilot data model"""
    id: int
    pilot_id: str
    name: str
    email: str
    airline_id: int
    rank_id: int
    home_airport_id: str
    curr_airport_id: str
    flights: int = 0
    flight_time: int = 0
    transfer_time: int = 0
    balance: float = 0.0
    timezone: str = "UTC"
    state: int = 1
    status: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Flight:
    """Flight data model"""
    id: int
    airline_id: int
    flight_number: str
    route_code: Optional[str] = None
    route_leg: Optional[int] = None
    dpt_airport_id: str = ""
    arr_airport_id: str = ""
    alt_airport_id: Optional[str] = None
    dpt_time: Optional[str] = None
    arr_time: Optional[str] = None
    flight_time: Optional[int] = None
    flight_type: int = 1
    distance: Optional[float] = None
    level: Optional[int] = None
    route: Optional[str] = None
    notes: Optional[str] = None
    active: bool = True
    visible: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Pirep:
    """Pilot Report data model"""
    id: int
    user_id: int
    airline_id: int
    aircraft_id: int
    flight_id: Optional[int] = None
    flight_number: Optional[str] = None
    route_code: Optional[str] = None
    route_leg: Optional[int] = None
    dpt_airport_id: str = ""
    arr_airport_id: str = ""
    level: Optional[int] = None
    distance: Optional[float] = None
    planned_distance: Optional[float] = None
    flight_time: Optional[int] = None
    planned_flight_time: Optional[int] = None
    zfw: Optional[float] = None
    block_fuel: Optional[float] = None
    fuel_used: Optional[float] = None
    landing_rate: Optional[float] = None
    score: Optional[int] = None
    source: int = PirepSource.MANUAL.value
    state: int = PirepState.DRAFT.value
    status: int = 0
    route: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    submitted_at: Optional[str] = None


@dataclass
class Aircraft:
    """Aircraft data model"""
    id: int
    subfleet_id: int
    airport_id: str
    iata: str
    icao: str
    name: str
    registration: str
    hex_code: Optional[str] = None
    zfw: Optional[float] = None
    mtow: Optional[float] = None
    state: int = AircraftState.PARKED.value
    status: int = AircraftStatus.ACTIVE.value
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Airport:
    """Airport data model"""
    id: str
    iata: Optional[str] = None
    icao: str = ""
    name: str = ""
    full_name: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    hub: bool = False
    timezone: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Airline:
    """Airline data model"""
    id: int
    icao: str
    iata: Optional[str] = None
    name: str = ""
    logo: Optional[str] = None
    country: Optional[str] = None
    active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Bid:
    """Flight bid data model"""
    id: int
    user_id: int
    flight_id: int
    aircraft_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Acars:
    """ACARS data model"""
    id: int
    pirep_id: int
    type: int
    nav_log: Optional[str] = None
    log: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance: Optional[float] = None
    heading: Optional[int] = None
    altitude: Optional[int] = None
    altitude_agl: Optional[int] = None
    altitude_msl: Optional[int] = None
    vs: Optional[int] = None
    gs: Optional[int] = None
    transponder: Optional[str] = None
    autopilot: Optional[str] = None
    fuel_flow: Optional[float] = None
    sim_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class PirepComment:
    """PIREP Comment data model"""
    id: int
    pirep_id: int
    user_id: int
    comment: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class News:
    """News data model"""
    id: int
    user_id: int
    subject: str
    body: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PhpVmsApiException(Exception):
    """Custom exception for phpVMS API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class PhpVmsApiClient:
    """
    phpVMS API Client

    A comprehensive client for interacting with the phpVMS API.
    Provides methods for all available endpoints including flights, PIREPs, users, ACARS, and more.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30):
        """
        Initialize the phpVMS API client

        Args:
            base_url: The base URL of the phpVMS installation (e.g., 'https://your-phpvms.com')
            api_key: API key for authentication (if required)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api"
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'phpVMS-Python-Client/1.0.0'
        })

        # Add API key to headers if provided
        if self.api_key:
            self.session.headers.update({
                'X-API-Key': self.api_key
            })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an HTTP request to the API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Dict containing the API response

        Raises:
            PhpVmsApiException: If the request fails
        """
        url = f"{self.api_base}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )

            # Handle different response types
            if response.headers.get('content-type', '').startswith('application/xml'):
                return {'data': response.text, 'content_type': 'xml'}

            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {'data': response.text}

            if not response.ok:
                raise PhpVmsApiException(
                    message=f"API request failed: {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    response=data
                )

            return data

        except requests.exceptions.RequestException as e:
            raise PhpVmsApiException(f"Request failed: {str(e)}")

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request"""
        return self._make_request('GET', endpoint, params=params)

    def _post(self, endpoint: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a POST request"""
        return self._make_request('POST', endpoint, data=data, json=json_data)

    def _put(self, endpoint: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a PUT request"""
        return self._make_request('PUT', endpoint, data=data, json=json_data)

    def _delete(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a DELETE request"""
        return self._make_request('DELETE', endpoint, params=params)

    # ==========================================
    # FLIGHT ENDPOINTS
    # ==========================================

    def get_flights(self, **params) -> Dict[str, Any]:
        """
        Get all flights with optional search parameters

        Args:
            **params: Search parameters (flight_id, airline_id, subfleet_id, flight_number,
                     route_code, dep_icao, arr_icao, dgt, dlt, ignore_restrictions, with)

        Returns:
            Dict containing flight data
        """
        return self._get('flights/search', params=params)

    def get_flight(self, flight_id: int, **params) -> Dict[str, Any]:
        """
        Get a specific flight by ID

        Args:
            flight_id: The flight ID
            **params: Additional parameters

        Returns:
            Dict containing flight data
        """
        return self._get(f'flights/{flight_id}', params=params)

    def get_flight_briefing(self, flight_id: int) -> Dict[str, Any]:
        """
        Get flight briefing (SimBrief data) for a flight

        Args:
            flight_id: The flight ID

        Returns:
            Dict containing briefing data (XML format)
        """
        return self._get(f'flights/{flight_id}/briefing')

    def get_flight_route(self, flight_id: int) -> Dict[str, Any]:
        """
        Get route data for a flight

        Args:
            flight_id: The flight ID

        Returns:
            Dict containing route data
        """
        return self._get(f'flights/{flight_id}/route')

    def get_flight_aircraft(self, flight_id: int) -> Dict[str, Any]:
        """
        Get available aircraft for a flight

        Args:
            flight_id: The flight ID

        Returns:
            Dict containing aircraft data
        """
        return self._get(f'flights/{flight_id}/aircraft')

    # ==========================================
    # USER ENDPOINTS
    # ==========================================

    def get_current_user(self, **params) -> Dict[str, Any]:
        """
        Get current authenticated user's profile

        Args:
            **params: Additional parameters (with)

        Returns:
            Dict containing user data
        """
        return self._get('user', params=params)

    def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        Get a specific user's profile

        Args:
            user_id: The user ID

        Returns:
            Dict containing user data
        """
        return self._get(f'users/{user_id}')

    def get_user_bids(self, user_id: Optional[int] = None, **params) -> Dict[str, Any]:
        """
        Get user's flight bids

        Args:
            user_id: User ID (optional, defaults to current user)
            **params: Additional parameters (with)

        Returns:
            Dict containing bid data
        """
        endpoint = 'user/bids'
        if user_id:
            params['id'] = user_id
        return self._get(endpoint, params=params)

    def add_bid(self, flight_id: int, aircraft_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Add a flight bid

        Args:
            flight_id: The flight ID to bid on
            aircraft_id: Optional aircraft ID
            user_id: User ID (optional, defaults to current user)

        Returns:
            Dict containing bid data
        """
        data = {'flight_id': flight_id}
        if aircraft_id:
            data['aircraft_id'] = aircraft_id
        if user_id:
            data['id'] = user_id

        return self._put('user/bids', json_data=data)

    def remove_bid(self, flight_id: Optional[int] = None, bid_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Remove a flight bid

        Args:
            flight_id: The flight ID (optional if bid_id provided)
            bid_id: The bid ID (optional if flight_id provided)
            user_id: User ID (optional, defaults to current user)

        Returns:
            Dict containing response
        """
        params = {}
        if flight_id:
            params['flight_id'] = flight_id
        if bid_id:
            params['bid_id'] = bid_id
        if user_id:
            params['id'] = user_id

        return self._delete('user/bids', params=params)

    def get_bid(self, bid_id: int) -> Dict[str, Any]:
        """
        Get a specific bid

        Args:
            bid_id: The bid ID

        Returns:
            Dict containing bid data
        """
        return self._get(f'user/bids/{bid_id}')

    def get_user_fleet(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get fleet/subfleets a user is allowed to access

        Args:
            user_id: User ID (optional, defaults to current user)

        Returns:
            Dict containing fleet data
        """
        params = {}
        if user_id:
            params['id'] = user_id
        return self._get('user/fleet', params=params)

    def get_user_pireps(self, user_id: Optional[int] = None, **params) -> Dict[str, Any]:
        """
        Get user's pilot reports

        Args:
            user_id: User ID (optional, defaults to current user)
            **params: Additional parameters (state, pagination)

        Returns:
            Dict containing PIREP data
        """
        if user_id:
            params['id'] = user_id
        return self._get('user/pireps', params=params)

    # ==========================================
    # PIREP ENDPOINTS
    # ==========================================

    def get_pirep(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get a specific PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing PIREP data
        """
        return self._get(f'pireps/{pirep_id}')

    def prefile_pirep(self, pirep_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new PIREP in prefile state

        Args:
            pirep_data: PIREP data dictionary

        Returns:
            Dict containing created PIREP data
        """
        return self._post('pireps/prefile', json_data=pirep_data)

    def update_pirep(self, pirep_id: int, pirep_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a PIREP

        Args:
            pirep_id: The PIREP ID
            pirep_data: Updated PIREP data

        Returns:
            Dict containing updated PIREP data
        """
        return self._put(f'pireps/{pirep_id}', json_data=pirep_data)

    def file_pirep(self, pirep_id: int, pirep_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File/submit a PIREP

        Args:
            pirep_id: The PIREP ID
            pirep_data: Final PIREP data

        Returns:
            Dict containing filed PIREP data
        """
        return self._post(f'pireps/{pirep_id}/file', json_data=pirep_data)

    def cancel_pirep(self, pirep_id: int) -> Dict[str, Any]:
        """
        Cancel a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing response
        """
        return self._delete(f'pireps/{pirep_id}/cancel')

    def get_pirep_comments(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get comments for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing comments data
        """
        return self._get(f'pireps/{pirep_id}/comments')

    def add_pirep_comment(self, pirep_id: int, comment: str) -> Dict[str, Any]:
        """
        Add a comment to a PIREP

        Args:
            pirep_id: The PIREP ID
            comment: Comment text

        Returns:
            Dict containing comment data
        """
        return self._post(f'pireps/{pirep_id}/comments', json_data={'comment': comment})

    def get_pirep_fields(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get custom fields for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing fields data
        """
        return self._get(f'pireps/{pirep_id}/fields')

    def set_pirep_fields(self, pirep_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set custom fields for a PIREP

        Args:
            pirep_id: The PIREP ID
            fields: Fields data

        Returns:
            Dict containing fields data
        """
        return self._post(f'pireps/{pirep_id}/fields', json_data={'fields': fields})

    def get_pirep_finances(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get financial transactions for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing financial data
        """
        return self._get(f'pireps/{pirep_id}/finances')

    def recalculate_pirep_finances(self, pirep_id: int) -> Dict[str, Any]:
        """
        Recalculate finances for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing updated financial data
        """
        return self._post(f'pireps/{pirep_id}/finances/recalculate')

    def get_pirep_route(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get route data for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing route data
        """
        return self._get(f'pireps/{pirep_id}/route')

    def set_pirep_route(self, pirep_id: int, route: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Set route data for a PIREP

        Args:
            pirep_id: The PIREP ID
            route: List of route points

        Returns:
            Dict containing response
        """
        return self._post(f'pireps/{pirep_id}/route', json_data={'route': route})

    def delete_pirep_route(self, pirep_id: int) -> Dict[str, Any]:
        """
        Delete route data for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing response
        """
        return self._delete(f'pireps/{pirep_id}/route')

    # ==========================================
    # ACARS ENDPOINTS
    # ==========================================

    def get_live_flights(self) -> Dict[str, Any]:
        """
        Get all active/live flights

        Returns:
            Dict containing live flight data
        """
        return self._get('acars/live')

    def get_flights_geojson(self) -> Dict[str, Any]:
        """
        Get all flights in GeoJSON format

        Returns:
            Dict containing GeoJSON data
        """
        return self._get('acars/geojson')

    def get_pirep_geojson(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get ACARS track for a PIREP in GeoJSON format

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing GeoJSON data
        """
        return self._get(f'acars/{pirep_id}/geojson')

    def get_acars_data(self, pirep_id: int) -> Dict[str, Any]:
        """
        Get ACARS flight path data for a PIREP

        Args:
            pirep_id: The PIREP ID

        Returns:
            Dict containing ACARS data
        """
        return self._get(f'acars/{pirep_id}')

    def post_acars_positions(self, pirep_id: int, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post ACARS position updates for a PIREP

        Args:
            pirep_id: The PIREP ID
            positions: List of position data

        Returns:
            Dict containing response
        """
        return self._post(f'acars/{pirep_id}/position', json_data={'positions': positions})

    def post_acars_logs(self, pirep_id: int, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post ACARS log entries for a PIREP

        Args:
            pirep_id: The PIREP ID
            logs: List of log entries

        Returns:
            Dict containing response
        """
        return self._post(f'acars/{pirep_id}/logs', json_data={'logs': logs})

    def post_acars_events(self, pirep_id: int, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post ACARS events for a PIREP

        Args:
            pirep_id: The PIREP ID
            events: List of event data

        Returns:
            Dict containing response
        """
        return self._post(f'acars/{pirep_id}/events', json_data={'events': events})

    # ==========================================
    # AIRLINE ENDPOINTS
    # ==========================================

    def get_airlines(self) -> Dict[str, Any]:
        """
        Get all airlines

        Returns:
            Dict containing airline data
        """
        return self._get('airlines')

    def get_airline(self, airline_id: int) -> Dict[str, Any]:
        """
        Get a specific airline

        Args:
            airline_id: The airline ID

        Returns:
            Dict containing airline data
        """
        return self._get(f'airlines/{airline_id}')

    # ==========================================
    # AIRPORT ENDPOINTS
    # ==========================================

    def get_airports(self, **params) -> Dict[str, Any]:
        """
        Get all airports

        Args:
            **params: Search parameters

        Returns:
            Dict containing airport data
        """
        return self._get('airports', params=params)

    def get_airport(self, airport_id: str) -> Dict[str, Any]:
        """
        Get a specific airport

        Args:
            airport_id: The airport ICAO code

        Returns:
            Dict containing airport data
        """
        return self._get(f'airports/{airport_id}')

    # ==========================================
    # FLEET ENDPOINTS
    # ==========================================

    def get_fleet(self) -> Dict[str, Any]:
        """
        Get fleet information

        Returns:
            Dict containing fleet data
        """
        return self._get('fleet')

    def get_aircraft(self, aircraft_id: int) -> Dict[str, Any]:
        """
        Get a specific aircraft

        Args:
            aircraft_id: The aircraft ID

        Returns:
            Dict containing aircraft data
        """
        return self._get(f'fleet/{aircraft_id}')

    # ==========================================
    # NEWS ENDPOINTS
    # ==========================================

    def get_news(self) -> Dict[str, Any]:
        """
        Get news/announcements

        Returns:
            Dict containing news data
        """
        return self._get('news')

    def get_news_item(self, news_id: int) -> Dict[str, Any]:
        """
        Get a specific news item

        Args:
            news_id: The news ID

        Returns:
            Dict containing news data
        """
        return self._get(f'news/{news_id}')

    # ==========================================
    # SETTINGS ENDPOINTS
    # ==========================================

    def get_settings(self) -> Dict[str, Any]:
        """
        Get system settings

        Returns:
            Dict containing settings data
        """
        return self._get('settings')

    # ==========================================
    # STATUS ENDPOINTS
    # ==========================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get system status

        Returns:
            Dict containing status data
        """
        return self._get('status')

    # ==========================================
    # MAINTENANCE ENDPOINTS
    # ==========================================

    def get_maintenance_status(self) -> Dict[str, Any]:
        """
        Get maintenance status

        Returns:
            Dict containing maintenance data
        """
        return self._get('maintenance')

    # ==========================================
    # UTILITY METHODS
    # ==========================================

    def to_dataclass(self, data: Dict[str, Any], model_class) -> Any:
        """
        Convert API response data to dataclass instance

        Args:
            data: Dictionary data from API
            model_class: Dataclass to convert to

        Returns:
            Instance of the specified dataclass
        """
        # Filter data to only include fields that exist in the dataclass
        if hasattr(model_class, '__dataclass_fields__'):
            valid_fields = model_class.__dataclass_fields__.keys()
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}
            return model_class(**filtered_data)
        return data

    def from_dataclass(self, obj: Any) -> Dict[str, Any]:
        """
        Convert dataclass instance to dictionary

        Args:
            obj: Dataclass instance

        Returns:
            Dictionary representation
        """
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        return obj


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

def create_client(base_url: str, api_key: Optional[str] = None, timeout: int = 30) -> PhpVmsApiClient:
    """
    Create a new phpVMS API client instance

    Args:
        base_url: The base URL of the phpVMS installation
        api_key: API key for authentication (if required)
        timeout: Request timeout in seconds

    Returns:
        PhpVmsApiClient instance
    """
    return PhpVmsApiClient(base_url=base_url, api_key=api_key, timeout=timeout)


# ==========================================
# EXAMPLE USAGE
# ==========================================

if __name__ == "__main__":
    # Example usage
    client = create_client("https://your-phpvms.com", api_key="your-api-key")

    try:
        # Get all flights
        flights = client.get_flights()
        print(f"Found {len(flights.get('data', []))} flights")

        # Get current user
        user = client.get_current_user()
        print(f"Current user: {user.get('data', {}).get('name', 'Unknown')}")

        # Get live flights
        live_flights = client.get_live_flights()
        print(f"Live flights: {len(live_flights.get('data', []))}")

    except PhpVmsApiException as e:
        print(f"API Error: {e.message}")
        if e.status_code:
            print(f"Status Code: {e.status_code}")
