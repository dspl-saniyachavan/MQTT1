import pytest
from src.core.database import DatabaseManager

def test_database_initialization(test_db_path):
    """Test database initialization"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()
    
    # Verify default users exist
    user = db.authenticate_user('admin@precisionpulse.com', 'admin123')
    assert user is not None
    assert user['role'] == 'admin'

def test_parameter_operations(test_db_path):
    """Test parameter CRUD operations"""
    db = DatabaseManager()
    db.db_path = test_db_path
    db.initialize_database()
    
    # Get enabled parameters
    params = db.get_enabled_parameters()
    assert len(params) > 0
    assert all('id' in p and 'name' in p for p in params)
