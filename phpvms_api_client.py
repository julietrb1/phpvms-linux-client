"""
phpVMS API Client

A comprehensive Python client for the phpVMS API.
This client provides access to all phpVMS API endpoints for flight simulation management.

Author: Generated for phpVMS API
Version: 1.0.0
"""

import json
import logging
from dataclasses import asdict
from enum import Enum
from typing import Dict, List, Optional, Any

import requests

from models import PirepState


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

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30, debug: bool = False):
        """
        Initialize the phpVMS API client

        Args:
            base_url: The base URL of the phpVMS installation (e.g., 'https://your-phpvms.com')
            api_key: API key for authentication (if required)
            timeout: Request timeout in seconds
            debug: Enable lightweight debug logging to stdout
        """
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api"
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()

        # Logging
        self._logger = logging.getLogger('phpvmsclient.api')
        self._debug = bool(debug)
        if self._debug:
            self._logger.setLevel(logging.DEBUG)
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s', datefmt='%H:%M:%S')
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)

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

    def set_debug(self, enabled: bool) -> None:
        """Enable or disable debug logging at runtime."""
        self._debug = bool(enabled)
        # Ensure a handler exists if enabling
        if self._debug:
            self._logger.setLevel(logging.DEBUG)
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s', datefmt='%H:%M:%S')
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
        else:
            # Keep handlers but lower logger level; debug logs are gated by self._debug anyway
            self._logger.setLevel(logging.WARNING)

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

        if self._debug:
            # Avoid dumping potentially large bodies; show keys instead
            json_keys = list((kwargs.get('json') or {}).keys()) if 'json' in kwargs else None
            self._logger.debug(f"REQ {method} {url} json_keys={json_keys}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs
            )

            if self._debug:
                self._logger.debug(f"RESP {response.status_code} {response.reason} for {method} {url}")

            # Handle different response types
            if response.headers.get('content-type', '').startswith('application/xml'):
                return {'data': response.text, 'content_type': 'xml'}

            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {'data': response.text}

            if not response.ok:
                # Log a concise error with a small snippet of the response
                snippet = response.text[:300] if hasattr(response, 'text') else ''
                self._logger.error(f"HTTP {response.status_code} {response.reason} on {method} {url} resp_snippet={snippet}")
                raise PhpVmsApiException(
                    message=f"API request failed: {response.status_code} - {response.reason}",
                    status_code=response.status_code,
                    response=data
                )

            return data

        except requests.exceptions.RequestException as e:
            self._logger.error(f"Request exception on {method} {url}: {e}")
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

    def get_pirep(self, pirep_id: str) -> Dict[str, Any]:
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
        Create a new PIREP and place it in a "inprogress" and "prefile" state
        Once ACARS updates are being processed, then it can go into an 'ENROUTE'
        status, and whatever other statuses may be defined

        Args:
            pirep_data: PIREP data dictionary

        Returns:
            Dict containing created PIREP data
        """
        return self._post('pireps/prefile', json_data=pirep_data)

    def update_pirep(self, pirep_id: str, pirep_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing PIREP
        Trigger PirepService::update via PUT /api/v1/pireps/{id}
        Args:
            pirep_id: The PIREP ID
            pirep_data: Updated PIREP data

        Returns:
            Dict containing updated PIREP data
        """
        # Use PUT to /pireps/{id} per phpVMS API spec
        return self._put(f'pireps/{pirep_id}', json_data=pirep_data)

    def file_pirep(self, pirep_id: int, pirep_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        File the PIREP

        Args:
            pirep_id: The PIREP ID
            pirep_data: Final PIREP data

        Returns:
            Dict containing filed PIREP data
        """
        return self._post(f'pireps/{pirep_id}/file', json_data=pirep_data)

    def cancel_pirep(self, pirep_id: str) -> Dict[str, Any]:
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

    def post_acars_position(self, pirep_id: int, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post ACARS position updates for a PIREP

        Args:
            pirep_id: The PIREP ID
            positions: List of position data

        Returns:
            Dict containing response
        """
        # phpVMS tests expect /pireps/{id}/acars/position
        return self._post(f'pireps/{pirep_id}/acars/position', json_data={'positions': positions})

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

def create_client(base_url: str, api_key: Optional[str] = None, timeout: int = 30, debug: bool = False) -> PhpVmsApiClient:
    """
    Create a new phpVMS API client instance

    Args:
        base_url: The base URL of the phpVMS installation
        api_key: API key for authentication (if required)
        timeout: Request timeout in seconds
        debug: Enable lightweight debug logging to stdout

    Returns:
        PhpVmsApiClient instance
    """
    return PhpVmsApiClient(base_url=base_url, api_key=api_key, timeout=timeout, debug=debug)


# ==========================================
# PIREP WORKFLOW SUPPORT
# ==========================================
class PirepStatus(Enum):
    """PIREP Flight Phase Status Codes (phpVMS)"""
    INITIATED = 'INI'
    BOARDING = 'BST'
    DEPARTED = 'OFB'
    TAXI = 'TXI'
    TAKEOFF = 'TOF'
    AIRBORNE = 'TKO'
    ENROUTE = 'ENR'
    APPROACH = 'TEN'
    LANDING = 'LDG'
    LANDED = 'LAN'
    ARRIVED = 'ARR'
    CANCELLED = 'DX'
    PAUSED = 'PSD'


class PirepStateMachine:
    """Enforces phpVMS PIREP workflow rules on the client side"""

    READ_ONLY_STATES = {PirepState.ACCEPTED.value, PirepState.REJECTED.value, PirepState.CANCELLED.value}
    NON_CANCELLABLE_STATES = {PirepState.ACCEPTED.value, PirepState.REJECTED.value, PirepState.CANCELLED.value, PirepState.DELETED.value}

    def can_update(self, pirep_state: int) -> bool:
        return pirep_state not in self.READ_ONLY_STATES

    def can_cancel(self, pirep_state: int) -> bool:
        return pirep_state not in self.NON_CANCELLABLE_STATES

    def get_next_actions(self, pirep_state: int):
        if pirep_state == PirepState.IN_PROGRESS.value:
            return ['update', 'file', 'cancel']
        elif pirep_state == PirepState.PENDING.value:
            return ['wait_for_approval']
        return []

class PirepWorkflowManager:
    """High-level PIREP workflow orchestration using PhpVmsApiClient"""

    def __init__(self, api_client: 'PhpVmsApiClient'):
        self.client = api_client
        self.state_machine = PirepStateMachine()

    def start_flight(self, flight_data: Dict[str, Any]) -> Dict[str, Any]:
        flight_data = dict(flight_data)
        pirep = self.client.prefile_pirep(flight_data)
        return pirep

    def update_flight(self, pirep_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        pirep = self.client.get_pirep(pirep_id)
        state = pirep.get('state')
        if state is None:
            raise PhpVmsApiException("PIREP response missing state", response=pirep)
        if not self.state_machine.can_update(int(state)):
            raise PhpVmsApiException("PIREP cannot be updated in current state", response=pirep)
        return self.client.update_pirep(pirep_id, update_data)

    def complete_flight(self, pirep_id: int, final_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.file_pirep(pirep_id, final_data)

    def cancel_flight(self, pirep_id: str) -> Dict[str, Any]:
        pirep = self.client.get_pirep(pirep_id)['data']
        state = pirep.get('state')
        if state is None:
            raise PhpVmsApiException("PIREP response missing state", response=pirep)
        if not self.state_machine.can_cancel(state):
            raise PhpVmsApiException("PIREP cannot be cancelled in current state", response=pirep)
        return self.client.cancel_pirep(pirep_id)
