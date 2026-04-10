"""
Telemetry Configuration
Defines streaming intervals and data collection parameters
MUST BE SYNCHRONIZED with frontend intervals
"""

# Telemetry streaming interval in milliseconds
# Frontend: TELEMETRY_FETCH_INTERVAL = 3000 (3 seconds)
# Backend: Should stream/update data at this interval
TELEMETRY_FETCH_INTERVAL_MS = 3000  # 3 seconds

# Convert to seconds for backend use
TELEMETRY_FETCH_INTERVAL_SECONDS = TELEMETRY_FETCH_INTERVAL_MS / 1000  # 3 seconds

# Maximum number of data points to keep in memory for charts
# Frontend displays last 20 data points
MAX_CHART_DATA_POINTS = 20

# Historical data retention
# How long to keep telemetry data in database (days)
TELEMETRY_RETENTION_DAYS = 30

# Data freshness threshold (seconds)
# If no data received within this time, mark as stale
DATA_STALE_THRESHOLD_SECONDS = 3

# Batch size for telemetry inserts
TELEMETRY_BATCH_SIZE = 100

# Configuration summary
CONFIG_SUMMARY = {
    'fetch_interval_ms': TELEMETRY_FETCH_INTERVAL_MS,
    'fetch_interval_seconds': TELEMETRY_FETCH_INTERVAL_SECONDS,
    'max_chart_points': MAX_CHART_DATA_POINTS,
    'retention_days': TELEMETRY_RETENTION_DAYS,
    'stale_threshold_seconds': DATA_STALE_THRESHOLD_SECONDS,
    'batch_size': TELEMETRY_BATCH_SIZE,
    'note': 'Frontend and backend must use same TELEMETRY_FETCH_INTERVAL_MS'
}
