import pytest
import sqlite3
from src.core.database import DatabaseManager

def test_database_initialization(test_db_path):
    """Test database initialization creates tables and default admin"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    user = db.authenticate_user('admin@precisionpulse.com', 'admin123')
    assert user is not None
    assert user['role'] == 'admin'

def test_parameter_operations(test_db_path):
    """Test parameter CRUD via direct SQLite insert then get_enabled_parameters"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    # Seed a parameter directly so get_enabled_parameters returns it
    conn = sqlite3.connect(test_db_path)
    conn.execute("INSERT OR IGNORE INTO parameters (id, name, unit, enabled) VALUES (1, 'Temperature', 'C', 1)")
    conn.commit()
    conn.close()

    params = db.get_enabled_parameters()
    assert len(params) > 0
    assert all('id' in p and 'name' in p for p in params)

def test_store_and_retrieve_parameter_stream(test_db_path):
    """Test storing and retrieving parameter stream data"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    conn = sqlite3.connect(test_db_path)
    conn.execute("INSERT OR IGNORE INTO parameters (id, name, unit, enabled) VALUES (1, 'Temp', 'C', 1)")
    conn.commit()
    conn.close()

    row_id = db.store_parameter_stream(parameter_id=1, value=42.5)
    assert row_id > 0

    data = db.get_parameter_stream_data(parameter_id=1, limit=10)
    assert len(data) > 0
    assert data[0]['value'] == 42.5

def test_buffer_and_retrieve_telemetry(test_db_path):
    """Test buffering telemetry when offline"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    conn = sqlite3.connect(test_db_path)
    conn.execute("INSERT OR IGNORE INTO parameters (id, name, unit, enabled) VALUES (1, 'Temp', 'C', 1)")
    conn.commit()
    conn.close()

    db.buffer_telemetry(parameter_id=1, value=99.9)
    buffered = db.get_buffered_data()
    assert len(buffered) > 0
    assert buffered[0]['value'] == 99.9

def test_mark_data_synced(test_db_path):
    """Test marking buffered data as synced"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    conn = sqlite3.connect(test_db_path)
    conn.execute("INSERT OR IGNORE INTO parameters (id, name, unit, enabled) VALUES (1, 'Temp', 'C', 1)")
    conn.commit()
    conn.close()

    db.buffer_telemetry(parameter_id=1, value=10.0)
    buffered = db.get_buffered_data()
    ids = [r['id'] for r in buffered]
    db.mark_data_synced(ids)
    db.delete_buffered_data(ids)
    assert db.get_buffered_data() == []

def test_config_set_and_get(test_db_path):
    """Test config key-value storage"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    db.set_config('TEST_KEY', 'hello')
    val = db.get_config('TEST_KEY')
    assert val == 'hello'

def test_check_permission(test_db_path):
    """Test permission check for roles"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()

    assert db.check_permission('admin', 'users', 'read') is True
    assert db.check_permission('user', 'livedata', 'read') is True
    assert db.check_permission('user', 'users', 'write') is False
