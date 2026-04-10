"""
Tests for Sync Ordering and Consistency Service
"""

import pytest
from datetime import datetime
from app.services.sync_ordering_service import (
    SyncOrderingService, SyncOperation, sync_ordering_service
)
from app.models.user import User
from app.models.parameter import Parameter
from app.models import db


class TestSyncOrdering:
    """Test sync operation ordering"""
    
    def test_create_sync_operation(self):
        """Test creating sync operation with sequence number"""
        service = SyncOrderingService()
        
        op = service.create_sync_operation(
            operation_type=SyncOperation.USER_CREATE,
            entity_id="test@example.com",
            data={'email': 'test@example.com', 'name': 'Test'},
            source='api'
        )
        
        assert op['sequence'] == 1
        assert op['operation_id'].startswith('api_user_create_')
        assert op['status'] == 'pending'
        assert op['type'] == 'user_create'
    
    def test_sequence_increments(self):
        """Test sequence numbers increment correctly"""
        service = SyncOrderingService()
        
        op1 = service.create_sync_operation(
            SyncOperation.USER_CREATE, "user1", {}, 'api'
        )
        op2 = service.create_sync_operation(
            SyncOperation.USER_CREATE, "user2", {}, 'api'
        )
        op3 = service.create_sync_operation(
            SyncOperation.USER_CREATE, "user3", {}, 'api'
        )
        
        assert op1['sequence'] == 1
        assert op2['sequence'] == 2
        assert op3['sequence'] == 3
    
    def test_operation_log_maintains_order(self):
        """Test operation log maintains insertion order"""
        service = SyncOrderingService()
        
        for i in range(5):
            service.create_sync_operation(
                SyncOperation.USER_CREATE, f"user{i}", {}, 'api'
            )
        
        log = service.get_operation_log()
        sequences = [op['sequence'] for op in log]
        
        assert sequences == [1, 2, 3, 4, 5]


class TestIdempotency:
    """Test idempotent operation execution"""
    
    def test_idempotent_user_create(self, app):
        """Test user create is idempotent"""
        service = SyncOrderingService()
        
        with app.app_context():
            op = service.create_sync_operation(
                SyncOperation.USER_CREATE,
                "test@example.com",
                {
                    'email': 'test@example.com',
                    'name': 'Test User',
                    'password_hash': 'hash123',
                    'role': 'user'
                },
                'api'
            )
            
            # First execution
            success1, result1, error1 = service.execute_operation(op)
            assert success1
            assert result1['action'] == 'created'
            
            # Second execution (replay) - should use cache
            success2, result2, error2 = service.execute_operation(op)
            assert success2
            assert result2['action'] == 'created'  # Cached result
            
            # Verify only one user created
            users = User.query.filter_by(email='test@example.com').all()
            assert len(users) == 1
    
    def test_idempotent_parameter_create(self, app):
        """Test parameter create is idempotent"""
        service = SyncOrderingService()
        
        with app.app_context():
            op = service.create_sync_operation(
                SyncOperation.PARAMETER_CREATE,
                "temperature",
                {
                    'name': 'Temperature',
                    'unit': 'C',
                    'description': 'Room temperature',
                    'enabled': True
                },
                'api'
            )
            
            # First execution
            success1, result1, error1 = service.execute_operation(op)
            assert success1
            assert result1['action'] == 'created'
            
            # Second execution (replay) - should use cache
            success2, result2, error2 = service.execute_operation(op)
            assert success2
            assert result2['action'] == 'created'  # Cached result
            
            # Verify only one parameter created
            params = Parameter.query.filter_by(name='Temperature').all()
            assert len(params) == 1
    
    def test_idempotent_user_delete(self, app):
        """Test user delete is idempotent"""
        service = SyncOrderingService()
        
        with app.app_context():
            # Create user first
            user = User(
                email='test@example.com',
                name='Test',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            op = service.create_sync_operation(
                SyncOperation.USER_DELETE,
                "test@example.com",
                {'email': 'test@example.com'},
                'api'
            )
            
            # First execution
            success1, result1, error1 = service.execute_operation(op)
            assert success1
            assert result1['action'] == 'deleted'
            
            # Second execution (replay) - should use cache
            success2, result2, error2 = service.execute_operation(op)
            assert success2
            assert result2['action'] == 'deleted'  # Cached result


class TestOrderedExecution:
    """Test ordered batch execution"""
    
    def test_execute_operations_in_order(self, app):
        """Test operations execute in sequence order"""
        service = SyncOrderingService()
        
        with app.app_context():
            ops = [
                service.create_sync_operation(
                    SyncOperation.USER_CREATE,
                    "user1@example.com",
                    {
                        'email': 'user1@example.com',
                        'name': 'User 1',
                        'password_hash': 'hash1',
                        'role': 'user'
                    },
                    'api'
                ),
                service.create_sync_operation(
                    SyncOperation.USER_CREATE,
                    "user2@example.com",
                    {
                        'email': 'user2@example.com',
                        'name': 'User 2',
                        'password_hash': 'hash2',
                        'role': 'user'
                    },
                    'api'
                ),
                service.create_sync_operation(
                    SyncOperation.PARAMETER_CREATE,
                    "temperature",
                    {
                        'name': 'Temperature',
                        'unit': 'C',
                        'enabled': True
                    },
                    'api'
                )
            ]
            
            results = service.execute_operations_ordered(ops)
            
            assert results['total'] == 3
            assert results['succeeded'] == 3
            assert results['failed'] == 0
            
            # Verify all created
            assert len(User.query.all()) == 2
            assert len(Parameter.query.all()) == 1
    
    def test_batch_stops_on_failure(self, app):
        """Test batch execution stops on first failure"""
        service = SyncOrderingService()
        
        with app.app_context():
            ops = [
                service.create_sync_operation(
                    SyncOperation.USER_CREATE,
                    "user1@example.com",
                    {
                        'email': 'user1@example.com',
                        'name': 'User 1',
                        'password_hash': 'hash1',
                        'role': 'user'
                    },
                    'api'
                ),
                service.create_sync_operation(
                    SyncOperation.USER_UPDATE,
                    "nonexistent@example.com",
                    {
                        'email': 'nonexistent@example.com',
                        'name': 'Nonexistent'
                    },
                    'api'
                ),
                service.create_sync_operation(
                    SyncOperation.USER_CREATE,
                    "user2@example.com",
                    {
                        'email': 'user2@example.com',
                        'name': 'User 2',
                        'password_hash': 'hash2',
                        'role': 'user'
                    },
                    'api'
                )
            ]
            
            results = service.execute_operations_ordered(ops)
            
            assert results['succeeded'] == 1
            assert results['failed'] == 1
            # Third operation should not execute
            assert len(results['operations']) == 2


class TestConsistencyVerification:
    """Test consistency verification"""
    
    def test_verify_consistency_no_issues(self, app):
        """Test consistency verification with valid state"""
        service = SyncOrderingService()
        
        with app.app_context():
            # Create valid data
            user = User(
                email='test@example.com',
                name='Test',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            
            param = Parameter(
                name='Temperature',
                unit='C',
                enabled=True
            )
            db.session.add(param)
            db.session.commit()
            
            consistency = service.verify_consistency()
            
            assert consistency['is_consistent']
            assert len(consistency['issues']) == 0
            assert consistency['total_users'] == 1
            assert consistency['total_parameters'] == 1
    
    def test_verify_consistency_reports_stats(self, app):
        """Test consistency verification reports correct statistics"""
        service = SyncOrderingService()
        
        with app.app_context():
            # Create multiple users and parameters
            for i in range(3):
                user = User(
                    email=f'user{i}@example.com',
                    name=f'User {i}',
                    password_hash='hash',
                    role='user'
                )
                db.session.add(user)
            
            for i in range(2):
                param = Parameter(
                    name=f'Param{i}',
                    unit='unit',
                    enabled=True
                )
                db.session.add(param)
            
            db.session.commit()
            
            consistency = service.verify_consistency()
            
            assert consistency['is_consistent']
            assert consistency['total_users'] == 3
            assert consistency['total_parameters'] == 2


class TestOperationRetrieval:
    """Test operation retrieval"""
    
    def test_get_operation_by_id(self):
        """Test retrieving operation by ID"""
        service = SyncOrderingService()
        
        op = service.create_sync_operation(
            SyncOperation.USER_CREATE,
            "test@example.com",
            {'email': 'test@example.com'},
            'api'
        )
        
        retrieved = service.get_operation_by_id(op['operation_id'])
        
        assert retrieved is not None
        assert retrieved['operation_id'] == op['operation_id']
        assert retrieved['sequence'] == op['sequence']
    
    def test_get_operation_log_limit(self):
        """Test operation log respects limit"""
        service = SyncOrderingService()
        
        for i in range(10):
            service.create_sync_operation(
                SyncOperation.USER_CREATE,
                f"user{i}",
                {},
                'api'
            )
        
        log = service.get_operation_log(limit=5)
        
        assert len(log) == 5
        assert log[0]['sequence'] == 6  # Last 5 operations


class TestRoleAndPermissionSync:
    """Test role and permission sync operations"""
    
    def test_role_change_operation(self, app):
        """Test role change operation"""
        service = SyncOrderingService()
        
        with app.app_context():
            # Create user
            user = User(
                email='test@example.com',
                name='Test',
                password_hash='hash',
                role='user'
            )
            db.session.add(user)
            db.session.commit()
            
            op = service.create_sync_operation(
                SyncOperation.ROLE_CHANGE,
                "test@example.com",
                {
                    'email': 'test@example.com',
                    'new_role': 'admin'
                },
                'api'
            )
            
            success, result, error = service.execute_operation(op)
            
            assert success
            assert result['old_role'] == 'user'
            assert result['new_role'] == 'admin'
            
            # Verify role changed
            user = User.query.filter_by(email='test@example.com').first()
            assert user.role == 'admin'
    
    def test_permission_change_operation(self, app):
        """Test permission change operation"""
        service = SyncOrderingService()
        
        with app.app_context():
            op = service.create_sync_operation(
                SyncOperation.PERMISSION_CHANGE,
                "admin",
                {
                    'role': 'admin',
                    'permissions': ['user.create', 'user.read', 'user.update', 'user.delete']
                },
                'api'
            )
            
            success, result, error = service.execute_operation(op)
            
            assert success
            assert result['role'] == 'admin'
            assert len(result['permissions']) == 4
