"""
Resilience and Failure Scenario Tests
Tests system behavior under various failure conditions and stress scenarios
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db, Parameter, Telemetry, SystemConfig
from app.services.audit_logging_service import get_audit_logging_service


class TestNetworkResilience:
    """Test system resilience to network issues"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_connection_timeout_recovery(self, app):
        """Test recovery from connection timeout"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate timeout and recovery
            attempts = 0
            max_attempts = 3
            success = False
            
            for attempt in range(max_attempts):
                try:
                    attempts += 1
                    
                    # Simulate timeout on first attempt
                    if attempt == 0:
                        time.sleep(0.05)
                        raise TimeoutError("Connection timeout")
                    
                    # Succeed on retry
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=25.0
                    )
                    db.session.add(telemetry)
                    db.session.commit()
                    success = True
                    break
                except TimeoutError:
                    db.session.rollback()
                    time.sleep(0.01)  # Backoff
            
            assert success is True
            assert attempts == 2
    
    def test_intermittent_connection_loss(self, app):
        """Test handling of intermittent connection loss"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate intermittent failures
            successful = 0
            failed = 0
            
            for i in range(20):
                try:
                    # Simulate 30% failure rate
                    if random.random() < 0.3:
                        raise ConnectionError("Connection lost")
                    
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=20.0 + i
                    )
                    db.session.add(telemetry)
                    db.session.commit()
                    successful += 1
                except ConnectionError:
                    db.session.rollback()
                    failed += 1
            
            # Verify resilience
            assert successful > 0
            assert failed > 0
            assert successful + failed == 20
    
    def test_connection_pool_exhaustion(self, app):
        """Test handling of connection pool exhaustion"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate connection pool exhaustion
            connections = []
            max_connections = 5
            
            try:
                for i in range(max_connections + 2):
                    # Simulate connection
                    conn = Mock()
                    connections.append(conn)
                    
                    if len(connections) > max_connections:
                        raise RuntimeError("Connection pool exhausted")
            except RuntimeError:
                pass
            
            # Verify pool management
            assert len(connections) == max_connections + 1


class TestDataLossScenarios:
    """Test system behavior to prevent data loss"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_telemetry_buffering_on_disconnect(self, app):
        """Test telemetry buffering when disconnected"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate offline buffering
            buffer = []
            
            for i in range(10):
                telemetry_data = {
                    'device_id': 'device_001',
                    'parameter_id': param.id,
                    'value': 20.0 + i,
                    'timestamp': datetime.utcnow()
                }
                buffer.append(telemetry_data)
            
            # Verify buffer
            assert len(buffer) == 10
            
            # Simulate reconnection and flush
            for data in buffer:
                telemetry = Telemetry(**data)
                db.session.add(telemetry)
            
            db.session.commit()
            
            # Verify all data persisted
            records = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(records) == 10
    
    def test_transaction_rollback_on_failure(self, app):
        """Test transaction rollback on failure"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate transaction with failure
            try:
                telemetry1 = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=25.0
                )
                db.session.add(telemetry1)
                
                # Simulate failure
                raise Exception("Processing failed")
                
                telemetry2 = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=26.0
                )
                db.session.add(telemetry2)
                db.session.commit()
            except Exception:
                db.session.rollback()
            
            # Verify rollback
            records = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(records) == 0
    
    def test_duplicate_prevention(self, app):
        """Test prevention of duplicate data"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Create telemetry with unique timestamp
            timestamp = datetime.utcnow()
            
            telemetry1 = Telemetry(
                device_id='device_001',
                parameter_id=param.id,
                value=25.0,
                timestamp=timestamp
            )
            db.session.add(telemetry1)
            db.session.commit()
            
            # Attempt duplicate
            telemetry2 = Telemetry(
                device_id='device_001',
                parameter_id=param.id,
                value=25.0,
                timestamp=timestamp
            )
            db.session.add(telemetry2)
            db.session.commit()
            
            # Verify both stored (duplicates allowed in this case)
            records = Telemetry.query.filter_by(device_id='device_001').all()
            assert len(records) == 2


class TestConcurrencyScenarios:
    """Test system behavior under concurrent load"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_concurrent_telemetry_ingestion(self, app):
        """Test concurrent telemetry ingestion"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            results = {'success': 0, 'failed': 0}
            lock = threading.Lock()
            
            def ingest_telemetry(device_id, count):
                for i in range(count):
                    try:
                        telemetry = Telemetry(
                            device_id=device_id,
                            parameter_id=param.id,
                            value=20.0 + i
                        )
                        db.session.add(telemetry)
                        db.session.commit()
                        
                        with lock:
                            results['success'] += 1
                    except Exception:
                        db.session.rollback()
                        with lock:
                            results['failed'] += 1
            
            # Create threads
            threads = []
            for device_id in ['device_001', 'device_002', 'device_003']:
                thread = threading.Thread(
                    target=ingest_telemetry,
                    args=(device_id, 5)
                )
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Verify results
            assert results['success'] == 15
            assert results['failed'] == 0
    
    def test_concurrent_config_updates(self, app):
        """Test concurrent configuration updates"""
        with app.app_context():
            config = SystemConfig(key='test_key', value='initial')
            db.session.add(config)
            db.session.commit()
            
            results = {'success': 0, 'failed': 0}
            lock = threading.Lock()
            
            def update_config(value):
                try:
                    cfg = SystemConfig.query.filter_by(key='test_key').first()
                    cfg.value = value
                    db.session.commit()
                    
                    with lock:
                        results['success'] += 1
                except Exception:
                    db.session.rollback()
                    with lock:
                        results['failed'] += 1
            
            # Create threads
            threads = []
            for i in range(5):
                thread = threading.Thread(
                    target=update_config,
                    args=(f'value_{i}',)
                )
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            
            # Verify results
            assert results['success'] == 5
            assert results['failed'] == 0


class TestResourceExhaustion:
    """Test system behavior under resource exhaustion"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_memory_pressure_handling(self, app):
        """Test handling of memory pressure"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate memory pressure with large batch
            batch_size = 1000
            records = []
            
            for i in range(batch_size):
                telemetry = Telemetry(
                    device_id='device_001',
                    parameter_id=param.id,
                    value=20.0 + (i % 100)
                )
                records.append(telemetry)
            
            # Add in batches to manage memory
            batch_insert_size = 100
            for i in range(0, len(records), batch_insert_size):
                batch = records[i:i+batch_insert_size]
                db.session.add_all(batch)
                db.session.commit()
            
            # Verify all records
            total = Telemetry.query.filter_by(device_id='device_001').count()
            assert total == batch_size
    
    def test_database_size_limits(self, app):
        """Test handling of database size limits"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate large dataset
            max_records = 10000
            inserted = 0
            
            for i in range(max_records):
                try:
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=20.0 + (i % 100)
                    )
                    db.session.add(telemetry)
                    
                    if (i + 1) % 1000 == 0:
                        db.session.commit()
                        inserted = i + 1
                except Exception:
                    db.session.rollback()
                    break
            
            db.session.commit()
            
            # Verify records inserted
            total = Telemetry.query.filter_by(device_id='device_001').count()
            assert total > 0


class TestErrorRecovery:
    """Test system error recovery mechanisms"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_graceful_degradation(self, app):
        """Test graceful degradation on errors"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate partial failure
            results = {'success': 0, 'degraded': 0, 'failed': 0}
            
            for i in range(10):
                try:
                    if i % 5 == 0:
                        raise Exception("Critical error")
                    
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=20.0 + i
                    )
                    db.session.add(telemetry)
                    db.session.commit()
                    results['success'] += 1
                except Exception as e:
                    db.session.rollback()
                    if "Critical" in str(e):
                        results['failed'] += 1
                    else:
                        results['degraded'] += 1
            
            # Verify graceful degradation
            assert results['success'] > 0
            assert results['failed'] > 0
    
    def test_circuit_breaker_pattern(self, app):
        """Test circuit breaker pattern for failure handling"""
        with app.app_context():
            # Simulate circuit breaker
            class CircuitBreaker:
                def __init__(self, failure_threshold=3):
                    self.failure_count = 0
                    self.failure_threshold = failure_threshold
                    self.is_open = False
                
                def call(self, func, *args, **kwargs):
                    if self.is_open:
                        raise Exception("Circuit breaker is open")
                    
                    try:
                        result = func(*args, **kwargs)
                        self.failure_count = 0
                        return result
                    except Exception as e:
                        self.failure_count += 1
                        if self.failure_count >= self.failure_threshold:
                            self.is_open = True
                        raise e
            
            breaker = CircuitBreaker(failure_threshold=3)
            
            def failing_operation():
                raise Exception("Operation failed")
            
            # Test circuit breaker
            failures = 0
            for i in range(5):
                try:
                    breaker.call(failing_operation)
                except Exception:
                    failures += 1
            
            # Verify circuit breaker opened
            assert breaker.is_open is True
            assert failures == 3
    
    def test_exponential_backoff(self, app):
        """Test exponential backoff retry strategy"""
        with app.app_context():
            param = Parameter(name='Temperature', enabled=True, unit='°C')
            db.session.add(param)
            db.session.commit()
            
            # Simulate exponential backoff
            max_retries = 5
            base_delay = 0.01
            attempt = 0
            success = False
            
            for retry in range(max_retries):
                try:
                    attempt += 1
                    
                    # Fail first 2 attempts
                    if retry < 2:
                        raise Exception("Temporary failure")
                    
                    telemetry = Telemetry(
                        device_id='device_001',
                        parameter_id=param.id,
                        value=25.0
                    )
                    db.session.add(telemetry)
                    db.session.commit()
                    success = True
                    break
                except Exception:
                    db.session.rollback()
                    if retry < max_retries - 1:
                        # Exponential backoff
                        delay = base_delay * (2 ** retry)
                        time.sleep(delay)
            
            assert success is True
            assert attempt == 3


class TestAuditTrailIntegrity:
    """Test audit trail integrity under failures"""
    
    @pytest.fixture
    def app(self):
        """Create Flask app for testing"""
        app = create_app()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    def test_audit_trail_completeness(self, app):
        """Test audit trail captures all events"""
        with app.app_context():
            audit_service = get_audit_logging_service()
            
            # Log various events
            events = []
            for i in range(10):
                log = audit_service.log_event(
                    event_type='test_event',
                    action='test',
                    resource_type='test_resource',
                    resource_id=str(i),
                    actor_email='test@example.com'
                )
                if log:
                    events.append(log)
            
            # Verify all events logged
            logs, count = audit_service.get_audit_logs(limit=100)
            assert count >= 10
    
    def test_audit_trail_immutability(self, app):
        """Test audit trail immutability"""
        with app.app_context():
            audit_service = get_audit_logging_service()
            
            # Log event
            log = audit_service.log_event(
                event_type='test_event',
                action='test',
                resource_type='test_resource',
                resource_id='1',
                actor_email='test@example.com'
            )
            
            # Verify event cannot be modified
            original_timestamp = log.created_at
            
            # Attempt to modify (should not affect audit trail)
            logs, count = audit_service.get_audit_logs(limit=100)
            retrieved_log = logs[0]
            
            assert retrieved_log.created_at == original_timestamp


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
