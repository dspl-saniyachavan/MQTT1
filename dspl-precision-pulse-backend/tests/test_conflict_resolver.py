"""
Unit tests for Conflict Resolution Service
"""

import pytest
from datetime import datetime, timedelta
from app.services.conflict_resolver import ConflictResolver


class TestConflictResolver:
    """Test conflict resolution using timestamps"""
    
    def test_resolve_conflict_remote_newer(self):
        """Test that remote data wins when it's newer"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Old Name',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'New Name',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert strategy == 'remote'
        assert resolved['name'] == 'New Name'
        assert resolved['updated_at'] == remote_data['updated_at']
    
    def test_resolve_conflict_local_newer(self):
        """Test that local data wins when it's newer"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'New Name',
            'updated_at': now.isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Old Name',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert strategy == 'local'
        assert resolved['name'] == 'New Name'
        assert resolved['updated_at'] == local_data['updated_at']
    
    def test_resolve_conflict_same_timestamp(self):
        """Test that remote wins when timestamps are equal"""
        now = datetime.utcnow().isoformat()
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'updated_at': now
        }
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'updated_at': now
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert strategy == 'remote'
        assert resolved['name'] == 'Remote Name'
    
    def test_resolve_conflict_missing_local(self):
        """Test resolution when local data is missing"""
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'updated_at': datetime.utcnow().isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(None, remote_data)
        
        assert strategy == 'default'
        assert resolved == remote_data
    
    def test_resolve_conflict_missing_remote(self):
        """Test resolution when remote data is missing"""
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'updated_at': datetime.utcnow().isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, None)
        
        assert strategy == 'default'
        assert resolved == local_data
    
    def test_resolve_conflicts_batch(self):
        """Test batch conflict resolution"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {
                    'id': 1,
                    'name': 'Old',
                    'updated_at': (now - timedelta(hours=1)).isoformat()
                },
                'remote': {
                    'id': 1,
                    'name': 'New',
                    'updated_at': now.isoformat()
                }
            },
            {
                'id': 2,
                'local': {
                    'id': 2,
                    'name': 'New',
                    'updated_at': now.isoformat()
                },
                'remote': {
                    'id': 2,
                    'name': 'Old',
                    'updated_at': (now - timedelta(hours=1)).isoformat()
                }
            }
        ]
        
        resolved = ConflictResolver.resolve_conflicts_batch(conflicts)
        
        assert len(resolved) == 2
        assert resolved[0]['strategy'] == 'remote'
        assert resolved[0]['data']['name'] == 'New'
        assert resolved[1]['strategy'] == 'local'
        assert resolved[1]['data']['name'] == 'New'
    
    def test_merge_field_changes(self):
        """Test field-by-field merge using timestamps"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'email': 'local@example.com',
            'updated_at': now.isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'email': 'remote@example.com',
            'updated_at': now.isoformat()
        }
        field_timestamps = {
            'name': {
                'local': (now - timedelta(hours=1)).isoformat(),
                'remote': now.isoformat()
            },
            'email': {
                'local': now.isoformat(),
                'remote': (now - timedelta(hours=1)).isoformat()
            }
        }
        
        merged = ConflictResolver.merge_field_changes(local_data, remote_data, field_timestamps)
        
        assert merged['name'] == 'Remote Name'  # Remote is newer
        assert merged['email'] == 'local@example.com'  # Local is newer
        assert merged['conflict_resolved'] is True
    
    def test_detect_conflicts(self):
        """Test conflict detection"""
        now = datetime.utcnow()
        local_records = [
            {
                'id': 1,
                'name': 'Local Name',
                'updated_at': (now - timedelta(hours=1)).isoformat()
            },
            {
                'id': 2,
                'name': 'Same',
                'updated_at': now.isoformat()
            }
        ]
        remote_records = [
            {
                'id': 1,
                'name': 'Remote Name',
                'updated_at': now.isoformat()
            },
            {
                'id': 2,
                'name': 'Same',
                'updated_at': now.isoformat()
            }
        ]
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        assert len(conflicts) == 1
        assert conflicts[0]['id'] == 1
        assert conflicts[0]['local']['name'] == 'Local Name'
        assert conflicts[0]['remote']['name'] == 'Remote Name'
    
    def test_get_conflict_summary(self):
        """Test conflict summary generation"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {
                    'updated_at': (now - timedelta(hours=1)).isoformat()
                },
                'remote': {
                    'updated_at': now.isoformat()
                }
            },
            {
                'id': 2,
                'local': {
                    'updated_at': now.isoformat()
                },
                'remote': {
                    'updated_at': (now - timedelta(hours=1)).isoformat()
                }
            }
        ]
        
        summary = ConflictResolver.get_conflict_summary(conflicts)
        
        assert summary['total_conflicts'] == 2
        assert summary['local_wins'] == 1
        assert summary['remote_wins'] == 1
        assert summary['local_win_percentage'] == 50.0
        assert summary['remote_win_percentage'] == 50.0
    
    def test_timestamp_parsing_iso_format(self):
        """Test ISO format timestamp parsing"""
        iso_timestamp = datetime.utcnow().isoformat()
        data = {'updated_at': iso_timestamp}
        
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_timestamp_parsing_datetime_object(self):
        """Test datetime object timestamp parsing"""
        now = datetime.utcnow()
        data = {'updated_at': now}
        
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed == now
    
    def test_timestamp_parsing_invalid(self):
        """Test invalid timestamp handling"""
        data = {'updated_at': 'invalid-timestamp'}
        
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is None
    
    def test_timestamp_parsing_missing(self):
        """Test missing timestamp handling"""
        data = {'name': 'Test'}
        
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is None
    
    def test_resolve_conflict_with_z_suffix(self):
        """Test timestamp parsing with Z suffix (UTC)"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Old',
            'updated_at': (now - timedelta(hours=1)).isoformat() + 'Z'
        }
        remote_data = {
            'id': 1,
            'name': 'New',
            'updated_at': now.isoformat() + 'Z'
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert strategy == 'remote'
        assert resolved['name'] == 'New'
    
    def test_complex_conflict_scenario(self):
        """Test complex conflict with multiple fields"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Alice',
            'email': 'alice@old.com',
            'role': 'admin',
            'updated_at': (now - timedelta(minutes=30)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Alice',
            'email': 'alice@new.com',
            'role': 'user',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert strategy == 'remote'
        assert resolved['email'] == 'alice@new.com'
        assert resolved['role'] == 'user'
        assert resolved['updated_at'] == remote_data['updated_at']
