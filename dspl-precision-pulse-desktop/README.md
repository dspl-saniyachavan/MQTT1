# PrecisionPulse Desktop

Real-time telemetry monitoring desktop app with MQTT streaming and zero-refresh UI.

## Features

- Live telemetry dashboard with responsive UI
- MQTT-based data streaming (3-second intervals)
- Zero-refresh parameter updates
- Offline data buffering with auto-sync
- Role-based access control (Admin, Client, User)
- Local SQLite database

## Quick Start

### Prerequisites
- Python 3.8+
- MQTT broker running (optional for standalone mode)

### Installation

```bash
# Clone repository
git clone https://github.com/DevAngles-Interns-2026/dspl-precision-pulse-desktop.git
cd dspl-precision-pulse-desktop

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MQTT broker settings
```

### Run Application

```bash
python main.py
```

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@precisionpulse.com | admin123 |
| Client | client@precisionpulse.com | client123 |
| User | user@precisionpulse.com | user123 |

## Configuration

Edit `.env` file:

```env
MQTT_BROKER=localhost
MQTT_PORT=8883
MQTT_USE_TLS=false
TELEMETRY_INTERVAL=3
DATABASE_PATH=data/precision_pulse.db
```

## Architecture

- **Frontend**: PySide6 (Qt6 for Python)
- **Database**: SQLite (local storage)
- **Streaming**: MQTT (paho-mqtt)
- **Authentication**: JWT + Argon2

## Key Features

### Zero-Refresh UI
- Parameter toggles update instantly without full page reload
- Only affected rows refresh, not entire table
- Smooth user experience

### Responsive Design
- Adaptive UI for different screen sizes
- Responsive margins and spacing
- Mobile-friendly layouts

### Data Sync
- Automatic parameter synchronization with backend
- Real-time dashboard updates
- Offline buffering with auto-sync on reconnect

## Project Structure

```
dspl-precision-pulse-desktop/
├── src/
│   ├── ui/              # UI components
│   ├── services/        # MQTT, sync services
│   ├── core/            # Database, auth
│   └── models/          # Data models
├── config/              # SSL certificates
├── data/                # Local database
├── main.py              # Entry point
└── requirements.txt     # Dependencies
```

## Development

### Running Tests
```bash
pytest
```

### Code Style
- Follow PEP 8
- Use type hints
- Document complex functions

## Troubleshooting

**App won't start:**
- Check Python version (3.8+)
- Verify all dependencies: `pip install -r requirements.txt`
- Check database permissions

**MQTT connection fails:**
- Verify broker is running
- Check MQTT_BROKER and MQTT_PORT in .env
- Ensure TLS certificates exist if MQTT_USE_TLS=true

**Database errors:**
- Delete `data/precision_pulse.db` to reset
- Check write permissions in data folder

## License

MIT License - See LICENSE file

## Support

For issues and questions, contact the development team.
