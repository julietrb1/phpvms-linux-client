# phpVMS Python API Client

A comprehensive Python client library for interacting with the phpVMS API. This client provides easy access to all phpVMS endpoints for flight simulation management systems.

## Features

- **Complete API Coverage**: Supports all phpVMS API endpoints including flights, PIREPs, users, ACARS, airlines, airports, and more
- **Type Safety**: Full dataclass models for all API entities with proper type hints
- **Authentication**: Built-in support for API key authentication
- **Error Handling**: Comprehensive exception handling with detailed error information
- **Easy to Use**: Pythonic interface with clear method names and documentation
- **Flexible**: Support for both raw dictionary responses and typed dataclass objects

## Installation

### Requirements

- Python 3.7+
- `requests` library

### Install Dependencies

```bash
pip install requests
```

### Download the Client

Simply download the `phpvms_api_client.py` file and place it in your project directory.

## Quick Start

```python
from phpvms_api_client import create_client, PhpVmsApiException

# Create a client instance
client = create_client("https://your-phpvms.com", api_key="your-api-key")

try:
    # Get all flights
    flights = client.get_flights()
    print(f"Found {len(flights['data'])} flights")
    
    # Get current user profile
    user = client.get_current_user()
    print(f"Welcome, {user['data']['name']}!")
    
    # Get live flights
    live_flights = client.get_live_flights()
    print(f"Currently {len(live_flights['data'])} flights in progress")
    
except PhpVmsApiException as e:
    print(f"API Error: {e.message}")
```

## Authentication

The phpVMS API may require authentication depending on your server configuration. You can authenticate using an API key:

```python
# With API key
client = create_client("https://your-phpvms.com", api_key="your-api-key")

# Without authentication (for public endpoints)
client = create_client("https://your-phpvms.com")
```

## API Endpoints

### Flight Operations

```python
# Search flights with parameters
flights = client.get_flights(
    airline_id=1,
    dep_icao="KJFK",
    arr_icao="KLAX"
)

# Get specific flight
flight = client.get_flight(123)

# Get flight briefing (SimBrief data)
briefing = client.get_flight_briefing(123)

# Get flight route
route = client.get_flight_route(123)

# Get available aircraft for flight
aircraft = client.get_flight_aircraft(123)
```

### User Management

```python
# Get current user
user = client.get_current_user()

# Get specific user
user = client.get_user(456)

# Get user's bids
bids = client.get_user_bids()

# Add a flight bid
bid = client.add_bid(flight_id=123, aircraft_id=789)

# Remove a bid
client.remove_bid(flight_id=123)

# Get user's fleet access
fleet = client.get_user_fleet()

# Get user's PIREPs
pireps = client.get_user_pireps(state=2)  # Accepted PIREPs
```

### PIREP (Pilot Report) Operations

```python
# Get a PIREP
pirep = client.get_pirep(789)

# Create a new PIREP (prefile)
pirep_data = {
    "airline_id": 1,
    "aircraft_id": 123,
    "flight_id": 456,
    "dpt_airport_id": "KJFK",
    "arr_airport_id": "KLAX",
    "flight_time": 360,  # minutes
    "distance": 2475,    # nautical miles
    "fuel_used": 15000   # lbs
}
new_pirep = client.prefile_pirep(pirep_data)

# Update a PIREP
updated_pirep = client.update_pirep(789, pirep_data)

# File/submit a PIREP
filed_pirep = client.file_pirep(789, pirep_data)

# Cancel a PIREP
client.cancel_pirep(789)

# PIREP comments
comments = client.get_pirep_comments(789)
new_comment = client.add_pirep_comment(789, "Great flight!")

# PIREP custom fields
fields = client.get_pirep_fields(789)
client.set_pirep_fields(789, {"weather": "Clear skies", "pax": "150"})

# PIREP finances
finances = client.get_pirep_finances(789)
client.recalculate_pirep_finances(789)

# PIREP route
route = client.get_pirep_route(789)
route_points = [
    {"lat": 40.6413, "lon": -73.7781, "altitude": 0},
    {"lat": 34.0522, "lon": -118.2437, "altitude": 35000}
]
client.set_pirep_route(789, route_points)
```

### ACARS (Flight Tracking)

```python
# Get live flights
live_flights = client.get_live_flights()

# Get flights in GeoJSON format
geojson = client.get_flights_geojson()

# Get PIREP track in GeoJSON
track = client.get_pirep_geojson(789)

# Get ACARS data for a PIREP
acars_data = client.get_acars_data(789)

# Post position updates
positions = [
    {
        "lat": 40.6413,
        "lon": -73.7781,
        "altitude": 35000,
        "heading": 270,
        "gs": 450,
        "sim_time": "2023-12-01T15:30:00Z"
    }
]
client.post_acars_position(789, positions)

# Post log entries
logs = [
    {
        "log": "Takeoff from KJFK",
        "sim_time": "2023-12-01T15:00:00Z"
    }
]
client.post_acars_logs(789, logs)

# Post events
events = [
    {
        "event": "GEAR_UP",
        "sim_time": "2023-12-01T15:05:00Z"
    }
]
client.post_acars_events(789, events)
```

### Airlines and Airports

```python
# Get all airlines
airlines = client.get_airlines()

# Get specific airline
airline = client.get_airline(1)

# Get all airports
airports = client.get_airports()

# Get specific airport
airport = client.get_airport("KJFK")
```

### Fleet Management

```python
# Get fleet information
fleet = client.get_fleet()

# Get specific aircraft
aircraft = client.get_aircraft(123)
```

### System Information

```python
# Get news/announcements
news = client.get_news()
news_item = client.get_news_item(1)

# Get system settings
settings = client.get_settings()

# Get system status
status = client.get_status()

# Get maintenance status
maintenance = client.get_maintenance_status()
```

## Data Models

The client includes comprehensive dataclass models for all API entities:

### User
```python
from phpvms_api_client import User

user_data = client.get_current_user()['data']
user = client.to_dataclass(user_data, User)
print(f"Pilot ID: {user.pilot_id}")
print(f"Flight Hours: {user.flight_time}")
```

### Flight
```python
from phpvms_api_client import Flight

flight_data = client.get_flight(123)['data']
flight = client.to_dataclass(flight_data, Flight)
print(f"Route: {flight.dpt_airport_id} -> {flight.arr_airport_id}")
```

### PIREP
```python
from phpvms_api_client import Pirep, PirepState

pirep_data = client.get_pirep(789)['data']
pirep = client.to_dataclass(pirep_data, Pirep)
print(f"State: {PirepState(pirep.state).name}")
```

### Available Models
- `User` - Pilot/user information
- `Flight` - Flight schedules and information
- `Pirep` - Pilot reports
- `Aircraft` - Aircraft information
- `Airport` - Airport data
- `Airline` - Airline information
- `Bid` - Flight bids
- `Acars` - ACARS tracking data
- `PirepComment` - PIREP comments
- `News` - News/announcements

### Enums
- `PirepState` - PIREP states (DRAFT, PENDING, ACCEPTED, REJECTED, CANCELLED)
- `PirepSource` - PIREP sources (MANUAL, ACARS)
- `AcarsType` - ACARS data types (FLIGHT_PATH, LOG, ROUTE)
- `AircraftState` - Aircraft states (PARKED, IN_USE, IN_AIR)
- `AircraftStatus` - Aircraft status (ACTIVE, MAINTENANCE, RETIRED)

## Error Handling

The client provides comprehensive error handling:

```python
from phpvms_api_client import PhpVmsApiException

try:
    flight = client.get_flight(999999)  # Non-existent flight
except PhpVmsApiException as e:
    print(f"Error: {e.message}")
    print(f"Status Code: {e.status_code}")
    print(f"Response: {e.response}")
```

## Advanced Usage

### Custom Timeout
```python
client = create_client("https://your-phpvms.com", timeout=60)
```

### Working with Raw Responses
```python
# Get raw response
response = client.get_flights()
flights_data = response['data']

# Convert to dataclass
from phpvms_api_client import Flight
flights = [client.to_dataclass(f, Flight) for f in flights_data]
```

### Pagination
Many endpoints support pagination:

```python
# Get flights with pagination
flights = client.get_flights(page=2, per_page=50)
```

### Search Parameters
```python
# Advanced flight search
flights = client.get_flights(
    airline_id=1,
    dep_icao="KJFK",
    arr_icao="KLAX",
    dgt=1000,  # Distance greater than 1000nm
    dlt=3000,  # Distance less than 3000nm
    ignore_restrictions=True
)
```

## API Reference

### Base URL Structure
All API endpoints follow the pattern: `{base_url}/api/v1/{endpoint}`

### Response Format
All responses follow the phpVMS API format:
```json
{
    "data": [...],
    "meta": {
        "pagination": {...}
    }
}
```

### Authentication
If authentication is required, include the API key in the Authorization header:
```
Authorization: Bearer your-api-key
```

## Contributing

This client was generated based on the phpVMS codebase analysis. If you find any issues or missing endpoints, please:

1. Check the phpVMS API documentation
2. Verify the endpoint exists in your phpVMS installation
3. Update the client accordingly

## License

This client is provided as-is for use with phpVMS installations. Please refer to the phpVMS project for licensing information.

## Support

For issues related to:
- **phpVMS API**: Check the [phpVMS documentation](https://docs.phpvms.net/)
- **This client**: Review the code and adapt as needed for your specific phpVMS version

## Version Compatibility

This client was generated for phpVMS 7.x. Some endpoints may vary depending on your phpVMS version and installed modules.
