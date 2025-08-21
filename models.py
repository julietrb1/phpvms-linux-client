from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PirepState(Enum):
    """PIREP Workflow States (phpVMS)"""
    IN_PROGRESS = 0
    PENDING = 1
    ACCEPTED = 2
    CANCELLED = 3
    DELETED = 4
    DRAFT = 5
    REJECTED = 6
    PAUSED = 7


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
    source: int = PirepSource.ACARS.value
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
