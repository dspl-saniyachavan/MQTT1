"""
Desktop Telemetry Configuration
Synchronizes with frontend and backend telemetry intervals
"""

# Telemetry streaming interval in milliseconds
# MUST MATCH:
# - Frontend: TELEMETRY_FETCH_INTERVAL = 3000
# - Backend: TELEMETRY_FETCH_INTERVAL_MS = 3000
TELEMETRY_INTERVAL_MS = 3000  # 3 seconds

# Convert to seconds for use in start_streaming()
TELEMETRY_INTERVAL_SECONDS = TELEMETRY_INTERVAL_MS // 1000  # 3 seconds

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 30

# Flush buffered data interval (milliseconds)
FLUSH_INTERVAL_MS = 5000  # 5 seconds

# Resume streaming delay after flush (milliseconds)
RESUME_DELAY_MS = 2000  # 2 seconds

# Configuration summary
CONFIG_SUMMARY = {
    'telemetry_interval_ms': TELEMETRY_INTERVAL_MS,
    'telemetry_interval_seconds': TELEMETRY_INTERVAL_SECONDS,
    'heartbeat_interval': HEARTBEAT_INTERVAL,
    'flush_interval_ms': FLUSH_INTERVAL_MS,
    'resume_delay_ms': RESUME_DELAY_MS,
    'note': 'Must match frontend (3000ms) and backend (3000ms) intervals'
}
