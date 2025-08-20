from typing import TypedDict, Optional, List, Union, Any, Dict

# Core resource types to consume phpVMS API responses

class Flight(TypedDict, total=False):
    """Type definition for Flight resource (matches API fields)"""
    id: Optional[int]
    airline_id: Optional[int]
    flight_number: Optional[str]
    route_code: Optional[str]
    route_leg: Optional[int]
    dpt_airport_id: Optional[str]
    arr_airport_id: Optional[str]
    alt_airport_id: Optional[str]
    dpt_time: Optional[str]
    arr_time: Optional[str]
    flight_time: Optional[int]  # minutes
    flight_type: Optional[int]
    distance: Optional[float]  # nautical miles
    level: Optional[int]
    route: Optional[str]
    notes: Optional[str]
    active: Optional[bool]
    visible: Optional[bool]
    created_at: Optional[str]
    updated_at: Optional[str]

class Fare(TypedDict, total=False):
    """Type definition for Fare resource (kept generic)"""
    id: Optional[int]
    name: Optional[str]
    price: Optional[float]
    cost: Optional[float]

class Aircraft(TypedDict, total=False):
    """Type definition for Aircraft resource (basic fields)"""
    id: Optional[int]
    subfleet_id: Optional[int]
    airport_id: Optional[str]
    iata: Optional[str]
    icao: Optional[str]
    name: Optional[str]
    registration: Optional[str]
    hex_code: Optional[str]
    zfw: Optional[float]
    mtow: Optional[float]
    state: Optional[int]
    status: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]

# Core resource types based on PHP resources

class Airline(TypedDict, total=False):
    """Type definition for Airline resource"""
    id: Optional[int]
    icao: Optional[str]
    iata: Optional[str]
    name: Optional[str]
    country: Optional[str]
    logo: Optional[str]
    active: Optional[bool]
    created_at: Optional[str]
    updated_at: Optional[str]

class UserBid(TypedDict, total=False):
    """Type definition for UserBid resource"""
    id: Optional[int]
    user_id: Optional[int]
    flight_id: Optional[int]
    aircraft_id: Optional[int]
    created_at: Optional[str]  # ISO datetime string
    updated_at: Optional[str]  # ISO datetime string
    flight: Optional[Flight]

class Subfleet(TypedDict, total=False):
    """Type definition for Subfleet resource"""
    id: Optional[int]
    name: Optional[str]
    type: Optional[str]
    fares: Optional[List[Fare]]
    aircraft: Optional[List[Aircraft]]

class Rank(TypedDict, total=False):
    """Type definition for Rank resource"""
    name: Optional[str]
    subfleets: Optional[List[Subfleet]]

class User(TypedDict, total=False):
    """Type definition for User resource (matches API fields)"""
    id: Optional[int]
    pilot_id: Optional[str]
    ident: Optional[str]
    name: Optional[str]
    name_private: Optional[str]
    email: Optional[str]
    avatar: Optional[str]
    discord_id: Optional[str]
    vatsim_id: Optional[str]
    ivao_id: Optional[str]
    airline_id: Optional[int]
    rank_id: Optional[int]
    home_airport_id: Optional[str]
    curr_airport_id: Optional[str]
    last_pirep_id: Optional[int]
    flights: Optional[int]
    flight_time: Optional[int]
    transfer_time: Optional[int]
    total_time: Optional[int]
    balance: Optional[float]
    timezone: Optional[str]
    state: Optional[int]
    status: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]
    # Nested resources
    airline: Optional[Airline]
    bids: Optional[List[UserBid]]
    rank: Optional[Rank]
    subfleets: Optional[List[Subfleet]]

class Pirep(TypedDict, total=False):
    """Type definition for PIREP resource (matches API fields)"""
    id: Optional[int]
    user_id: Optional[int]
    airline_id: Optional[int]
    aircraft_id: Optional[int]
    flight_id: Optional[int]
    flight_number: Optional[str]
    route_code: Optional[str]
    route_leg: Optional[int]
    dpt_airport_id: Optional[str]
    arr_airport_id: Optional[str]
    level: Optional[int]
    distance: Optional[float]  # Ensure numeric
    planned_distance: Optional[float]
    flight_time: Optional[int]  # minutes
    planned_flight_time: Optional[int]
    zfw: Optional[float]
    block_fuel: Optional[float]
    fuel_used: Optional[float]
    landing_rate: Optional[float]
    score: Optional[int]
    source: Optional[int]
    state: Optional[int]
    status: Optional[int]
    route: Optional[str]
    notes: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    submitted_at: Optional[str]
    # Common nested resources returned by API
    user: Optional[User]
    airline: Optional[Airline]
    aircraft: Optional[Aircraft]
    flight: Optional[Flight]
    comments: Optional[List[Dict[str, Any]]]
    fields: Optional[Dict[str, Any]]

# Utility functions for type checking and validation

def is_user_type(data: Any) -> bool:
    """Check if data matches User type structure"""
    if not isinstance(data, dict):
        return False
    expected_fields = {'id', 'pilot_id', 'name'}
    return any(field in data for field in expected_fields)

def is_airline_type(data: Any) -> bool:
    """Check if data matches Airline type structure"""
    if not isinstance(data, dict):
        return False
    expected_fields = {'id', 'icao', 'name'}
    return any(field in data for field in expected_fields)

def is_user_bid_type(data: Any) -> bool:
    """Check if data matches UserBid type structure"""
    if not isinstance(data, dict):
        return False
    expected_fields = {'id', 'user_id', 'flight_id'}
    return any(field in data for field in expected_fields)

def is_rank_type(data: Any) -> bool:
    """Check if data matches Rank type structure"""
    if not isinstance(data, dict):
        return False
    return 'name' in data

def is_subfleet_type(data: Any) -> bool:
    """Check if data matches Subfleet type structure"""
    if not isinstance(data, dict):
        return False
    return 'fares' in data or 'aircraft' in data or 'id' in data

# Export all types for easy importing
__all__ = [
    'User', 'Airline', 'UserBid', 'Rank', 'Subfleet',
    'Flight', 'Fare', 'Aircraft', 'Pirep',
    'is_user_type', 'is_airline_type', 'is_user_bid_type',
    'is_rank_type', 'is_subfleet_type'
]
