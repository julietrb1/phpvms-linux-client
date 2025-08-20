# phpVMS PySide UI Client

A simple and intuitive GUI application built with PySide6 that demonstrates authentication and PIREP listing using the phpVMS API client.

## Features

- **User Authentication**: Login with phpVMS base URL and API key
- **User Information Display**: Shows pilot details, flight statistics, and current status
- **PIREP Management**: View and manage previous Pilot Reports (PIREPs)
- **Real-time Updates**: Background API calls with progress indicators
- **Clean Interface**: Modern, responsive UI with proper error handling

## Screenshots

The application provides:
- Login screen with URL and API key fields
- User information panel showing pilot details
- PIREPs table with flight history, routes, aircraft, and status
- Status bar with real-time feedback
- Logout functionality

## Requirements

- Python 3.7 or higher
- PySide6 (Qt for Python)
- requests library
- phpvms_api_client.py (included)

## Installation

### 1. Set up a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv phpvms_ui_env

# Activate virtual environment
# On Windows:
phpvms_ui_env\Scripts\activate
# On macOS/Linux:
source phpvms_ui_env/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Installation

Make sure you have all required files in the same directory:
- `phpvms_ui_client.py` - Main UI application
- `phpvms_api_client.py` - API client library
- `requirements.txt` - Dependencies list
- `README_UI_CLIENT.md` - This documentation

## Usage

### Starting the Application

```bash
python phpvms_ui_client.py
```

### Login Process

1. **Enter Base URL**: Your phpVMS installation URL (e.g., `https://your-phpvms.com`)
2. **Enter API Key**: Your personal API key from phpVMS user profile
3. **Click Login**: The application will authenticate and load your data

### Getting Your API Key

1. Log into your phpVMS web interface
2. Go to your user profile/settings
3. Look for "API Key" or "API Token" section
4. Copy the key for use in the application

### Main Interface

After successful login, you'll see:

#### User Information Panel (Left)
- **Name**: Your pilot name
- **Pilot ID**: Your unique pilot identifier
- **Airline ID**: Your assigned airline
- **Rank ID**: Your current rank
- **Total Flights**: Number of completed flights
- **Flight Time**: Total flight hours and minutes
- **Current Airport**: Your current location

#### PIREPs Table (Right)
- **ID**: PIREP identifier
- **Flight**: Flight number
- **Route**: Departure → Arrival airports
- **Aircraft**: Aircraft ID used
- **State**: PIREP status (DRAFT, PENDING, ACCEPTED, etc.)
- **Date**: When the PIREP was created
- **Flight Time**: Duration of the flight
- **Distance**: Flight distance in nautical miles

### Features

#### Refresh PIREPs
Click the "Refresh" button to reload your PIREP data from the server.

#### Logout
Click the "Logout" button in the status bar to return to the login screen.

#### Error Handling
The application provides clear error messages for:
- Invalid URLs or API keys
- Network connection issues
- API server errors
- Authentication failures

## Troubleshooting

### Common Issues

#### Import Errors
```
ModuleNotFoundError: No module named 'PySide6'
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

#### API Client Not Found
```
Error importing phpVMS API client
```
**Solution**: Ensure `phpvms_api_client.py` is in the same directory

#### Connection Errors
```
Connection error: [Errno 11001] getaddrinfo failed
```
**Solution**: Check your internet connection and phpVMS URL

#### Authentication Errors
```
API Error: Unauthorized
```
**Solution**: Verify your API key is correct and active

### Debug Mode

For debugging, you can modify the application to show more detailed error information:

1. Open `phpvms_ui_client.py`
2. Find the exception handling sections
3. Add `traceback.print_exc()` for detailed error traces

## Development

### Project Structure

```
phpvms/
├── phpvms_api_client.py      # API client library
├── phpvms_ui_client.py       # Main UI application
├── requirements.txt          # Dependencies
├── README_UI_CLIENT.md       # This documentation
└── test_ui_structure.py      # Structure validation test
```

### Key Components

#### ApiWorker Class
- Handles API calls in background threads
- Prevents UI freezing during network operations
- Emits signals for UI updates

#### LoginWidget Class
- Provides login form interface
- Validates input fields
- Emits login requests

#### UserInfoWidget Class
- Displays user/pilot information
- Updates dynamically after login

#### PirepsWidget Class
- Shows PIREPs in a sortable table
- Handles data formatting and display
- Provides refresh functionality

#### MainWindow Class
- Main application window
- Coordinates all widgets
- Manages application state

### Extending the Application

You can extend the application by:

1. **Adding More API Endpoints**: Use the comprehensive API client to add flights, bids, etc.
2. **Improving the UI**: Add more detailed views, charts, or maps
3. **Adding Features**: Flight planning, bid management, ACARS tracking
4. **Customizing Display**: Themes, layouts, or additional data fields

### API Client Integration

The UI uses the phpVMS API client which provides access to:
- User management
- Flight operations
- PIREP management
- ACARS data
- Fleet information
- And much more...

See `README_API_CLIENT.md` for complete API documentation.

## Configuration

### Default Settings

The application includes some default settings:
- Default URL: `https://demo.phpvms.net` (for testing)
- Timeout: 30 seconds for API calls
- Window size: 800x600 minimum

### Customization

You can modify these settings in `phpvms_ui_client.py`:

```python
# In LoginWidget.setup_ui()
self.base_url_input.setText("https://your-default-url.com")

# In PhpVmsApiClient creation
client = create_client(base_url, api_key=api_key, timeout=60)
```

## Security Notes

- API keys are handled securely in memory
- Passwords are masked in the UI
- No credentials are stored permanently
- All API communication uses HTTPS (recommended)

## Contributing

To contribute to this project:

1. Test the application with your phpVMS installation
2. Report bugs or suggest improvements
3. Submit pull requests with enhancements
4. Help improve documentation

## License

This UI client is provided as-is for use with phpVMS installations. Please refer to the phpVMS project for licensing information.

## Support

For support:

1. **phpVMS Issues**: Check the [phpVMS documentation](https://docs.phpvms.net/)
2. **API Issues**: Refer to `README_API_CLIENT.md`
3. **UI Issues**: Check this documentation and the code comments
4. **General Help**: Ensure all requirements are installed and files are in the correct location

## Version History

- **v1.0.0**: Initial release with login, user info, and PIREP listing
- Features: PySide6 GUI, background API calls, error handling, logout functionality

## Future Enhancements

Potential future features:
- Flight booking and bid management
- Real-time flight tracking with maps
- ACARS data visualization
- Detailed flight planning tools
- Statistics and reporting
- Multi-user support
- Settings persistence
- Themes and customization options

---

**Note**: This application requires a working phpVMS installation with API access enabled. Make sure your phpVMS server supports the API endpoints used by this client.
