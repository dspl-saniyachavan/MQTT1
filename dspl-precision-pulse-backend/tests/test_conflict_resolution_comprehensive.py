"""
Unit tests for Conflict Resolution
Tests timestamp-based conflict resolution, field merging, and edge cases
"""

import pytest
from datetime import datetime, timedelta
from app.services.conflict_resolver import ConflictResolver


class TestConflictResolutionBasics:
    """Test basic conflict resolution"""
    
    def test_resolve_conflict_remote_newer(self):
        """Test resolving conflict when remote is newer"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert strategy == 'remote'
    
    def test_resolve_conflict_local_newer(self):
        """Test resolving conflict when local is newer"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local',
            'updated_at': now.isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == local_data
        assert strategy == 'local'
    
    def test_resolve_conflict_same_timestamp_uses_remote(self):
        """Test that same timestamp defaults to remote"""
        now = datetime.utcnow()
        timestamp = now.isoformat()
        local_data = {
            'id': 1,
            'name': 'Local',
            'updated_at': timestamp
        }
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': timestamp
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert strategy == 'remote'
    
    def test_resolve_conflict_missing_local_data(self):
        """Test resolving conflict with missing local data"""
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': datetime.utcnow().isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(None, remote_data)
        
        assert resolved == remote_data
        assert strategy == 'default'
    
    def test_resolve_conflict_missing_remote_data(self):
        """Test resolving conflict with missing remote data"""
        local_data = {
            'id': 1,
            'name': 'Local',
            'updated_at': datetime.utcnow().isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, None)
        
        assert resolved == local_data
        assert strategy == 'default'
    
    def test_resolve_conflict_both_missing(self):
        """Test resolving conflict with both data missing"""
        resolved, strategy = ConflictResolver.resolve_conflict(None, None)
        
        assert resolved is None
        assert strategy == 'default'


class TestTimestampParsing:
    """Test timestamp parsing"""
    
    def test_parse_iso_format_timestamp(self):
        """Test parsing ISO format timestamp"""
        now = datetime.utcnow()
        timestamp_str = now.isoformat()
        
        data = {'id': 1, 'updated_at': timestamp_str}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_parse_iso_format_with_z_suffix(self):
        """Test parsing ISO format with Z suffix"""
        timestamp_str = '2024-01-15T10:30:45.123Z'
        
        data = {'id': 1, 'updated_at': timestamp_str}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_parse_standard_format_timestamp(self):
        """Test parsing standard format timestamp"""
        timestamp_str = '2024-01-15 10:30:45'
        
        data = {'id': 1, 'updated_at': timestamp_str}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_parse_timestamp_with_microseconds(self):
        """Test parsing timestamp with microseconds"""
        timestamp_str = '2024-01-15 10:30:45.123456'
        
        data = {'id': 1, 'updated_at': timestamp_str}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is not None
        assert isinstance(parsed, datetime)
    
    def test_parse_datetime_object(self):
        """Test parsing datetime object"""
        now = datetime.utcnow()
        
        data = {'id': 1, 'updated_at': now}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed == now
    
    def test_parse_invalid_timestamp_returns_none(self):
        """Test that invalid timestamp returns None"""
        data = {'id': 1, 'updated_at': 'invalid-timestamp'}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is None
    
    def test_parse_missing_timestamp_returns_none(self):
        """Test that missing timestamp returns None"""
        data = {'id': 1}
        parsed = ConflictResolver._get_timestamp(data)
        
        assert parsed is None


class TestBatchConflictResolution:
    """Test batch conflict resolution"""
    
    def test_resolve_multiple_conflicts(self):
        """Test resolving multiple conflicts"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {'id': 1, 'name': 'Local1', 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 1, 'name': 'Remote1', 'updated_at': now.isoformat()}
            },
            {
                'id': 2,
                'local': {'id': 2, 'name': 'Local2', 'updated_at': now.isoformat()},
                'remote': {'id': 2, 'name': 'Remote2', 'updated_at': (now - timedelta(hours=1)).isoformat()}
            }
        ]
        
        resolved = ConflictResolver.resolve_conflicts_batch(conflicts)
        
        assert len(resolved) == 2
        assert resolved[0]['data']['name'] == 'Remote1'
        assert resolved[0]['strategy'] == 'remote'
        assert resolved[1]['data']['name'] == 'Local2'
        assert resolved[1]['strategy'] == 'local'
    
    def test_batch_resolution_includes_metadata(self):
        """Test that batch resolution includes metadata"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {'id': 1, 'name': 'Local', 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 1, 'name': 'Remote', 'updated_at': now.isoformat()}
            }
        ]
        
        resolved = ConflictResolver.resolve_conflicts_batch(conflicts)
        
        assert 'id' in resolved[0]
        assert 'data' in resolved[0]
        assert 'strategy' in resolved[0]
        assert 'local_timestamp' in resolved[0]
        assert 'remote_timestamp' in resolved[0]
        assert 'resolved_at' in resolved[0]
    
    def test_batch_resolution_empty_list(self):
        """Test batch resolution with empty list"""
        resolved = ConflictResolver.resolve_conflicts_batch([])
        
        assert resolved == []
    
    def test_batch_resolution_large_batch(self):
        """Test batch resolution with large number of conflicts"""
        now = datetime.utcnow()
        conflicts = []
        
        for i in range(100):
            conflicts.append({
                'id': i,
                'local': {'id': i, 'name': f'Local{i}', 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': i, 'name': f'Remote{i}', 'updated_at': now.isoformat()}
            })
        
        resolved = ConflictResolver.resolve_conflicts_batch(conflicts)
        
        assert len(resolved) == 100
        for item in resolved:
            assert item['strategy'] == 'remote'


class TestFieldMerging:
    """Test field-by-field merging"""
    
    def test_merge_field_changes_remote_newer(self):
        """Test merging when remote field is newer"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'email': 'local@example.com',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'email': 'remote@example.com',
            'updated_at': now.isoformat()
        }
        field_timestamps = {
            'name': {
                'local': (now - timedelta(hours=2)).isoformat(),
                'remote': (now - timedelta(minutes=30)).isoformat()
            },
            'email': {
                'local': (now - timedelta(hours=1)).isoformat(),
                'remote': (now - timedelta(minutes=15)).isoformat()
            }
        }
        
        merged = ConflictResolver.merge_field_changes(local_data, remote_data, field_timestamps)
        
        assert merged['name'] == 'Remote Name'
        assert merged['email'] == 'remote@example.com'
        assert merged['conflict_resolved'] is True
    
    def test_merge_field_changes_mixed_timestamps(self):
        """Test merging with mixed field timestamps"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'email': 'local@example.com',
            'phone': 'local-phone'
        }
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'email': 'remote@example.com',
            'phone': 'remote-phone'
        }
        field_timestamps = {
            'name': {
                'local': (now - timedelta(hours=2)).isoformat(),
                'remote': (now - timedelta(minutes=30)).isoformat()
            },
            'email': {
                'local': (now - timedelta(minutes=15)).isoformat(),
                'remote': (now - timedelta(hours=1)).isoformat()
            },
            'phone': {
                'local': now.isoformat(),
                'remote': (now - timedelta(hours=1)).isoformat()
            }
        }
        
        merged = ConflictResolver.merge_field_changes(local_data, remote_data, field_timestamps)
        
        assert merged['name'] == 'Remote Name'  # Remote newer
        assert merged['email'] == 'local@example.com'  # Local newer
        assert merged['phone'] == 'local-phone'  # Local newer
    
    def test_merge_field_changes_partial_fields(self):
        """Test merging with only some fields having timestamps"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local Name',
            'email': 'local@example.com'
        }
        remote_data = {
            'id': 1,
            'name': 'Remote Name',
            'email': 'remote@example.com'
        }
        field_timestamps = {
            'name': {
                'local': (now - timedelta(hours=1)).isoformat(),
                'remote': now.isoformat()
            }
        }
        
        merged = ConflictResolver.merge_field_changes(local_data, remote_data, field_timestamps)
        
        assert merged['name'] == 'Remote Name'
        assert merged['email'] == 'local@example.com'  # Unchanged


class TestConflictDetection:
    """Test conflict detection"""
    
    def test_detect_conflicts_in_records(self):
        """Test detecting conflicts between records"""
        now = datetime.utcnow()
        local_records = [
            {'id': 1, 'name': 'Local1', 'updated_at': (now - timedelta(hours=1)).isoformat()},
            {'id': 2, 'name': 'Local2', 'updated_at': now.isoformat()}
        ]
        remote_records = [
            {'id': 1, 'name': 'Remote1', 'updated_at': now.isoformat()},
            {'id': 2, 'name': 'Local2', 'updated_at': now.isoformat()}
        ]
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        assert len(conflicts) == 1
        assert conflicts[0]['id'] == 1
    
    def test_detect_conflicts_no_conflicts(self):
        """Test detecting conflicts when there are none"""
        now = datetime.utcnow()
        local_records = [
            {'id': 1, 'name': 'Same', 'updated_at': now.isoformat()}
        ]
        remote_records = [
            {'id': 1, 'name': 'Same', 'updated_at': now.isoformat()}
        ]
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        assert len(conflicts) == 0
    
    def test_detect_conflicts_missing_in_local(self):
        """Test detecting conflicts when record missing in local"""
        now = datetime.utcnow()
        local_records = []
        remote_records = [
            {'id': 1, 'name': 'Remote', 'updated_at': now.isoformat()}
        ]
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        assert len(conflicts) == 0  # Not a conflict, just missing
    
    def test_detect_conflicts_missing_in_remote(self):
        """Test detecting conflicts when record missing in remote"""
        now = datetime.utcnow()
        local_records = [
            {'id': 1, 'name': 'Local', 'updated_at': now.isoformat()}
        ]
        remote_records = []
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        assert len(conflicts) == 0  # Not a conflict, just missing
    
    def test_detect_conflicts_same_timestamp_different_data(self):
        """Test detecting conflicts with same timestamp but different data"""
        now = datetime.utcnow()
        timestamp = now.isoformat()
        local_records = [
            {'id': 1, 'name': 'Local', 'updated_at': timestamp}
        ]
        remote_records = [
            {'id': 1, 'name': 'Remote', 'updated_at': timestamp}
        ]
        
        conflicts = ConflictResolver.detect_conflicts(local_records, remote_records)
        
        # Same timestamp with different data is not detected as conflict
        # (conflict detection requires timestamp difference)
        assert len(conflicts) == 0


class TestConflictSummary:
    """Test conflict summary statistics"""
    
    def test_get_conflict_summary_all_local_wins(self):
        """Test summary when all local conflicts win"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {'id': 1, 'updated_at': now.isoformat()},
                'remote': {'id': 1, 'updated_at': (now - timedelta(hours=1)).isoformat()}
            },
            {
                'id': 2,
                'local': {'id': 2, 'updated_at': now.isoformat()},
                'remote': {'id': 2, 'updated_at': (now - timedelta(hours=1)).isoformat()}
            }
        ]
        
        summary = ConflictResolver.get_conflict_summary(conflicts)
        
        assert summary['total_conflicts'] == 2
        assert summary['local_wins'] == 2
        assert summary['remote_wins'] == 0
        assert summary['local_win_percentage'] == 100.0
        assert summary['remote_win_percentage'] == 0.0
    
    def test_get_conflict_summary_all_remote_wins(self):
        """Test summary when all remote conflicts win"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {'id': 1, 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 1, 'updated_at': now.isoformat()}
            },
            {
                'id': 2,
                'local': {'id': 2, 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 2, 'updated_at': now.isoformat()}
            }
        ]
        
        summary = ConflictResolver.get_conflict_summary(conflicts)
        
        assert summary['total_conflicts'] == 2
        assert summary['local_wins'] == 0
        assert summary['remote_wins'] == 2
        assert summary['local_win_percentage'] == 0.0
        assert summary['remote_win_percentage'] == 100.0
    
    def test_get_conflict_summary_mixed_wins(self):
        """Test summary with mixed wins"""
        now = datetime.utcnow()
        conflicts = [
            {
                'id': 1,
                'local': {'id': 1, 'updated_at': now.isoformat()},
                'remote': {'id': 1, 'updated_at': (now - timedelta(hours=1)).isoformat()}
            },
            {
                'id': 2,
                'local': {'id': 2, 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 2, 'updated_at': now.isoformat()}
            },
            {
                'id': 3,
                'local': {'id': 3, 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': 3, 'updated_at': now.isoformat()}
            }
        ]
        
        summary = ConflictResolver.get_conflict_summary(conflicts)
        
        assert summary['total_conflicts'] == 3
        assert summary['local_wins'] == 1
        assert summary['remote_wins'] == 2
        assert summary['local_win_percentage'] == pytest.approx(33.33, 0.1)
        assert summary['remote_win_percentage'] == pytest.approx(66.67, 0.1)
    
    def test_get_conflict_summary_empty_list(self):
        """Test summary with empty conflict list"""
        summary = ConflictResolver.get_conflict_summary([])
        
        assert summary['total_conflicts'] == 0
        assert summary['local_wins'] == 0
        assert summary['remote_wins'] == 0
        assert summary['local_win_percentage'] == 0.0
        assert summary['remote_win_percentage'] == 0.0


class TestConflictResolutionEdgeCases:
    """Test edge cases in conflict resolution"""
    
    def test_resolve_conflict_with_null_values(self):
        """Test resolving conflict with null values"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': None,
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert resolved['name'] == 'Remote'
    
    def test_resolve_conflict_with_empty_strings(self):
        """Test resolving conflict with empty strings"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': '',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert resolved['name'] == 'Remote'
    
    def test_resolve_conflict_with_special_characters(self):
        """Test resolving conflict with special characters"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': 'Local™®©',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': 'Remote™®©',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert resolved['name'] == 'Remote™®©'
    
    def test_resolve_conflict_with_unicode(self):
        """Test resolving conflict with unicode characters"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'name': '本地',
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'name': '远程',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert resolved['name'] == '远程'
    
    def test_resolve_conflict_with_large_data(self):
        """Test resolving conflict with large data"""
        now = datetime.utcnow()
        large_string = 'x' * 10000
        local_data = {
            'id': 1,
            'data': large_string,
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'data': large_string + 'y',
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert len(resolved['data']) == 10001
    
    def test_resolve_conflict_with_nested_objects(self):
        """Test resolving conflict with nested objects"""
        now = datetime.utcnow()
        local_data = {
            'id': 1,
            'metadata': {'key': 'local_value'},
            'updated_at': (now - timedelta(hours=1)).isoformat()
        }
        remote_data = {
            'id': 1,
            'metadata': {'key': 'remote_value'},
            'updated_at': now.isoformat()
        }
        
        resolved, strategy = ConflictResolver.resolve_conflict(local_data, remote_data)
        
        assert resolved == remote_data
        assert resolved['metadata']['key'] == 'remote_value'


class TestConflictResolutionPerformance:
    """Test performance characteristics"""
    
    def test_resolve_single_conflict_performance(self):
        """Test single conflict resolution is fast"""
        now = datetime.utcnow()
        local_data = {'id': 1, 'name': 'Local', 'updated_at': (now - timedelta(hours=1)).isoformat()}
        remote_data = {'id': 1, 'name': 'Remote', 'updated_at': now.isoformat()}
        
        import time
        start = time.time()
        for _ in range(1000):
            ConflictResolver.resolve_conflict(local_data, remote_data)
        elapsed = time.time() - start
        
        # Should complete 1000 resolutions in less than 100ms
        assert elapsed < 0.1
    
    def test_batch_resolution_performance(self):
        """Test batch resolution performance"""
        now = datetime.utcnow()
        conflicts = []
        for i in range(100):
            conflicts.append({
                'id': i,
                'local': {'id': i, 'updated_at': (now - timedelta(hours=1)).isoformat()},
                'remote': {'id': i, 'updated_at': now.isoformat()}
            })
        
        import time
        start = time.time()
        ConflictResolver.resolve_conflicts_batch(conflicts)
        elapsed = time.time() - start
        
        # Should complete batch of 100 in less than 50ms
        assert elapsed < 0.05
    
    def test_detect_conflicts_performance(self):
        """Test conflict detection performance"""
        now = datetime.utcnow()
        local_records = []
        remote_records = []
        
        for i in range(100):
            local_records.append({'id': i, 'updated_at': (now - timedelta(hours=1)).isoformat()})
            remote_records.append({'id': i, 'updated_at': now.isoformat()})
        
        import time
        start = time.time()
        ConflictResolver.detect_conflicts(local_records, remote_records)
        elapsed = time.time() - start
        
        # Should complete detection of 100 records in less than 50ms
        assert elapsed < 0.05
