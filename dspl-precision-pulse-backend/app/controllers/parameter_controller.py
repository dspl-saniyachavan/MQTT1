from flask import request, jsonify, g
from app.models.parameter import Parameter
from app.models import db
from sqlalchemy.exc import IntegrityError
from marshmallow import Schema, fields, ValidationError
from app.services.sync_service import sync_service
from app.services.audit_logging_service import get_audit_logging_service
from datetime import datetime, timezone

_PARAM_EXISTS = 'Parameter with this name already exists'
_PARAM_NOT_FOUND = 'Parameter not found'

class ParameterSchema(Schema):
    name = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    unit = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    description = fields.Str(allow_none=True, load_default="")
    enabled = fields.Bool(load_default=True)
    alert_min = fields.Float(allow_none=True, load_default=None)
    alert_max = fields.Float(allow_none=True, load_default=None)
    warn_min = fields.Float(allow_none=True, load_default=None)
    warn_max = fields.Float(allow_none=True, load_default=None)

class ParameterController:
    @staticmethod
    def get_all_parameters():
        try:
            parameters = Parameter.query.order_by(Parameter.created_at.desc()).all()
            return {'parameters': [param.to_dict() for param in parameters]}, 200
        except Exception as e:
            return {'error': f'Failed to fetch parameters: {str(e)}'}, 500
    
    @staticmethod
    def create_parameter(data):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        schema = ParameterSchema()
        try:
            validated_data = schema.load(data)
        except ValidationError as err:
            return {'error': 'Validation failed', 'details': err.messages}, 400
        
        try:
            # Check if parameter name already exists
            existing = Parameter.query.filter_by(name=validated_data['name'].strip()).first()
            if existing:
                return {'error': _PARAM_EXISTS}, 409
            
            parameter = Parameter(
                name=validated_data['name'].strip(),
                unit=validated_data['unit'].strip(),
                description=validated_data.get('description', '').strip(),
                enabled=validated_data.get('enabled', True),
                alert_min=validated_data.get('alert_min'),
                alert_max=validated_data.get('alert_max'),
                warn_min=validated_data.get('warn_min'),
                warn_max=validated_data.get('warn_max'),
            )
            
            db.session.add(parameter)
            db.session.commit()
            
            # Log parameter creation
            audit_service.log_event(
                event_type='parameter_created',
                action='create',
                resource_type='parameter',
                resource_id=str(parameter.id),
                resource_name=parameter.name,
                actor_email=actor_email,
                new_values={
                    'name': parameter.name,
                    'unit': parameter.unit,
                    'description': parameter.description,
                    'enabled': parameter.enabled
                },
                description=f'Parameter {parameter.name} created'
            )
            
            # Sync to SQLite — pass full dict so id is available
            sync_service.sync_parameter_to_sqlite(parameter.to_dict())

            # Publish MQTT sync message
            ParameterController._publish_parameter_sync(parameter.to_dict(), 'create')
            
            return {'message': 'Parameter created successfully', 'parameter': parameter.to_dict()}, 201
            
        except IntegrityError:
            db.session.rollback()
            return {'error': _PARAM_EXISTS}, 409
        except Exception as e:
            db.session.rollback()
            audit_service.log_event(
                event_type='parameter_creation_failed',
                action='create',
                resource_type='parameter',
                resource_name=validated_data.get('name', 'unknown'),
                actor_email=actor_email,
                status='failure',
                error_message=str(e),
                severity='error'
            )
            return {'error': f'Failed to create parameter: {str(e)}'}, 500
    
    @staticmethod
    def get_parameter_by_id(param_id):
        try:
            parameter = Parameter.query.get(param_id)
            if not parameter:
                return {'error': _PARAM_NOT_FOUND}, 404
            return {'parameter': parameter.to_dict()}, 200
        except Exception as e:
            return {'error': f'Failed to fetch parameter: {str(e)}'}, 500
    
    @staticmethod
    def update_parameter(param_id, data):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        schema = ParameterSchema(partial=True)
        try:
            validated_data = schema.load(data)
        except ValidationError as err:
            return {'error': 'Validation failed', 'details': err.messages}, 400
        
        try:
            parameter = Parameter.query.get(param_id)
            if not parameter:
                return {'error': _PARAM_NOT_FOUND}, 404
            
            # Capture old values
            old_values = {
                'name': parameter.name,
                'unit': parameter.unit,
                'description': parameter.description,
                'enabled': parameter.enabled
            }
            
            # Check name uniqueness if name is being updated
            if 'name' in validated_data:
                existing = Parameter.query.filter(
                    Parameter.name == validated_data['name'].strip(),
                    Parameter.id != param_id
                ).first()
                if existing:
                    return {'error': _PARAM_EXISTS}, 409
            
            # Update fields
            for key, value in validated_data.items():
                if key in ['name', 'unit', 'description']:
                    setattr(parameter, key, value.strip() if isinstance(value, str) else value)
                elif key in ['alert_min', 'alert_max', 'warn_min', 'warn_max']:
                    setattr(parameter, key, value)
                else:
                    setattr(parameter, key, value)
            
            db.session.commit()
            
            # If parameter was just disabled, close any open alert events for it
            if 'enabled' in validated_data and not validated_data['enabled']:
                try:
                    from app.models.alert_event import AlertEvent
                    from datetime import datetime, timezone
                    open_events = AlertEvent.query.filter_by(
                        parameter_id=param_id, resolved_at=None
                    ).all()
                    if open_events:
                        now = datetime.now(timezone.utc)
                        for ev in open_events:
                            ev.resolved_at = now
                        db.session.commit()
                        # Emit resolved for each
                        try:
                            from app import get_socketio
                            sio = get_socketio()
                            if sio:
                                for ev in open_events:
                                    sio.emit('alert_resolved', ev.to_dict(), namespace='/')
                        except Exception:
                            pass
                        logger.info('[PARAM] Closed %d open alert events for disabled parameter %s',
                                    len(open_events), parameter.name) if False else None
                        print(f'[PARAM] Closed {len(open_events)} open alert events for disabled parameter {parameter.name}')
                except Exception as ae:
                    print(f'[PARAM] Error closing alert events on disable: {ae}')
            
            # Capture new values
            new_values = {
                'name': parameter.name,
                'unit': parameter.unit,
                'description': parameter.description,
                'enabled': parameter.enabled
            }
            
            # Log parameter update
            audit_service.log_event(
                event_type='parameter_updated',
                action='update',
                resource_type='parameter',
                resource_id=str(parameter.id),
                resource_name=parameter.name,
                actor_email=actor_email,
                old_values=old_values,
                new_values=new_values,
                description=f'Parameter {parameter.name} updated'
            )
            
            # Sync to SQLite — pass full dict so id is available
            sync_service.sync_parameter_to_sqlite(parameter.to_dict())

            # Publish MQTT sync message
            ParameterController._publish_parameter_sync(parameter.to_dict(), 'update')
            
            return {'message': 'Parameter updated successfully', 'parameter': parameter.to_dict()}, 200
            
        except IntegrityError:
            db.session.rollback()
            return {'error': _PARAM_EXISTS}, 409
        except Exception as e:
            db.session.rollback()
            audit_service.log_event(
                event_type='parameter_update_failed',
                action='update',
                resource_type='parameter',
                resource_id=str(param_id),
                actor_email=actor_email,
                status='failure',
                error_message=str(e),
                severity='error'
            )
            return {'error': f'Failed to update parameter: {str(e)}'}, 500
    
    @staticmethod
    def delete_parameter(param_id):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        try:
            parameter = Parameter.query.get(param_id)
            if not parameter:
                return {'error': _PARAM_NOT_FOUND}, 404
            
            param_dict = parameter.to_dict()
            param_name = parameter.name
            
            db.session.delete(parameter)
            db.session.commit()
            
            # Log parameter deletion
            audit_service.log_event(
                event_type='parameter_deleted',
                action='delete',
                resource_type='parameter',
                resource_id=str(param_id),
                resource_name=param_name,
                actor_email=actor_email,
                description=f'Parameter {param_name} deleted'
            )
            
            # Sync deletion to SQLite
            try:
                import sqlite3
                with sqlite3.connect(sync_service.sqlite_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM parameters WHERE name = ?', (param_name,))
                    conn.commit()
            except Exception as e:
                print(f"Error syncing parameter deletion to SQLite: {e}")
            
            # Publish MQTT sync message
            print(f"📤 Publishing parameter delete sync: {param_name} (ID: {param_dict['id']})")
            ParameterController._publish_parameter_sync(param_dict, 'delete')
            
            return {'message': 'Parameter deleted successfully'}, 200
            
        except Exception as e:
            db.session.rollback()
            audit_service.log_event(
                event_type='parameter_deletion_failed',
                action='delete',
                resource_type='parameter',
                resource_id=str(param_id),
                actor_email=actor_email,
                status='failure',
                error_message=str(e),
                severity='error'
            )
            return {'error': f'Failed to delete parameter: {str(e)}'}, 500
    
    @staticmethod
    def _publish_parameter_sync(parameter_data, action):
        """Publish parameter sync via the existing MQTTPublisher (reuses TLS connection)."""
        try:
            from app.services.mqtt_publisher import get_mqtt_publisher
            import uuid
            from datetime import datetime, timezone
            pub = get_mqtt_publisher()
            msg_id = str(uuid.uuid4())
            payload = {
                'type': f'parameter_{action}d' if action in ('create', 'update', 'delete') else f'parameter_{action}',
                'msg_id': msg_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'action': action,
                'parameter': parameter_data,
                'source': 'backend',
            }
            # Also emit via Socket.IO so frontend updates immediately
            try:
                from app import get_socketio
                sio = get_socketio()
                if sio:
                    event = {'create': 'parameter_created', 'update': 'parameter_updated', 'delete': 'parameter_deleted'}.get(action, f'parameter_{action}')
                    sio.emit(event, {'parameter': parameter_data}, namespace='/')
            except Exception as se:
                import logging; logging.getLogger(__name__).warning('[PARAM] Socket.IO emit error: %s', se)
            pub._publish('precisionpulse/sync/parameters', payload)
        except Exception as e:
            import logging; logging.getLogger(__name__).error('[PARAM] publish_parameter_sync error: %s', e)
