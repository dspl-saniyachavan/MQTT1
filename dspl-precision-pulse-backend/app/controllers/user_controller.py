_USER_NOT_FOUND = 'User not found'
from app.models.user import User
from app.models import db
from app.services.sync_service import sync_service
from app.services.audit_logging_service import get_audit_logging_service
from app.services.mqtt_publisher import get_mqtt_publisher
from app.services.remote_commands_service import remote_commands_service
from app.services.buffer_service import buffer_service
from flask import g, current_app

class UserController:
    @staticmethod
    def get_all_users():
        users = User.query.all()
        return [user.to_dict() for user in users], 200
    
    @staticmethod
    def create_user(email, name, password, role='user'):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        if User.query.filter_by(email=email).first():
            return {'error': 'Email already exists'}, 409
        
        user = User(email=email, name=name, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Log user creation
        audit_service.log_user_created(
            user_id=user.id,
            user_email=user.email,
            new_values={
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'is_active': user.is_active
            },
            actor_email=actor_email
        )
        
        # Sync to SQLite
        sync_service.sync_user_to_sqlite({
            'email': user.email,
            'name': user.name,
            'password_hash': user.password_hash,
            'role': user.role,
            'is_active': user.is_active,
            'avatar_url': getattr(user, 'avatar_url', None)
        })
        
        # Publish user creation via MQTT or buffer if disconnected
        user_data = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'is_active': user.is_active,
            'password_hash': user.password_hash,
        }
        try:
            mqtt_pub = get_mqtt_publisher()
            if mqtt_pub.connected:
                mqtt_pub.publish_user_created(user_data)
            else:
                buffer_service.buffer_user_change(user.id, user.email, 'create', user_data)
        except Exception as e:
            print(f"[USER_CONTROLLER] Error publishing user creation: {e}")
        
        # Broadcast via WebSocket for real-time frontend update
        try:
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit(
                    'user_created',
                    {'user': user_data},
                    namespace='/'
                )
        except Exception as e:
            print(f"[USER_CONTROLLER] Error broadcasting user creation: {e}")

        # Send sync_users command to all desktops
        try:
            remote_commands_service.send_user_sync_command(
                action='user_created',
                params={'user': user_data},
                user_email=actor_email
            )
        except Exception as e:
            print(f"[USER_CONTROLLER] Error sending sync_users command: {e}")

        return user.to_dict(), 201
    
    @staticmethod
    def update_user(user_id, **kwargs):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        user = User.query.get(user_id)
        if not user:
            return {'error': _USER_NOT_FOUND}, 404
        
        # Capture old values
        old_values = {
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'is_active': user.is_active
        }
        
        for key, value in kwargs.items():
            if key == 'password':
                user.set_password(value)
            elif key == 'password_hash':
                user.password_hash = value
            elif hasattr(user, key):
                setattr(user, key, value)
        
        db.session.commit()
        
        # Capture new values
        new_values = {
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'is_active': user.is_active
        }
        
        # Log user update
        audit_service.log_user_updated(
            user_id=user.id,
            user_email=user.email,
            old_values=old_values,
            new_values=new_values,
            actor_email=actor_email
        )
        
        # Sync to SQLite
        sync_service.sync_user_to_sqlite({
            'email': user.email,
            'name': user.name,
            'password_hash': user.password_hash,
            'role': user.role,
            'is_active': user.is_active,
            'avatar_url': user.avatar_url
        })
        
        # Publish user update via MQTT or buffer if disconnected
        user_data = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'role': user.role,
            'is_active': user.is_active,
            'avatar_url': user.avatar_url
        }
        try:
            mqtt_pub = get_mqtt_publisher()
            if mqtt_pub.connected:
                mqtt_pub.publish_user_updated(user_data)
                if old_values.get('role') != new_values.get('role'):
                    mqtt_pub.publish_role_changed(
                        user_id=user.id,
                        email=user.email,
                        old_role=old_values.get('role'),
                        new_role=new_values.get('role')
                    )
            else:
                buffer_service.buffer_user_change(user.id, user.email, 'update', user_data)
        except Exception as e:
            print(f"[USER_CONTROLLER] Error publishing user update: {e}")

        # Broadcast via WebSocket for real-time frontend update
        try:
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit(
                    'user_updated',
                    {'user': user_data},
                    namespace='/'
                )
        except Exception as e:
            print(f"[USER_CONTROLLER] Error broadcasting user update: {e}")

        # Send sync_users command to all desktops
        try:
            action = 'role_changed' if old_values.get('role') != new_values.get('role') else 'user_updated'
            params = {'user': user_data}
            if action == 'role_changed':
                params.update({'user_id': user.id, 'old_role': old_values.get('role'), 'new_role': new_values.get('role')})
            remote_commands_service.send_user_sync_command(action=action, params=params, user_email=actor_email)
        except Exception as e:
            print(f"[USER_CONTROLLER] Error sending sync_users command: {e}")

        return user.to_dict(), 200
    
    @staticmethod
    def delete_user(user_id):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        user = User.query.get(user_id)
        if not user:
            return {'error': _USER_NOT_FOUND}, 404
        
        user_email = user.email
        
        db.session.delete(user)
        db.session.commit()
        
        # Log user deletion
        audit_service.log_user_deleted(
            user_id=user_id,
            user_email=user_email,
            actor_email=actor_email
        )
        
        # Sync deletion to SQLite
        try:
            import sqlite3
            with sqlite3.connect(sync_service.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users WHERE email = ?', (user_email,))
                conn.commit()
        except Exception as e:
            print(f"Error syncing user deletion to SQLite: {e}")
        
        # Publish user deletion via MQTT or buffer if disconnected
        try:
            mqtt_pub = get_mqtt_publisher()
            if mqtt_pub.connected:
                mqtt_pub.publish_user_deleted(user_id, user_email)
            else:
                buffer_service.buffer_user_change(user_id, user_email, 'delete', {'id': user_id, 'email': user_email})
        except Exception as e:
            print(f"[USER_CONTROLLER] Error publishing user deletion: {e}")

        # Broadcast via WebSocket for real-time frontend update
        try:
            if hasattr(current_app, 'socketio'):
                current_app.socketio.emit(
                    'user_deleted',
                    {'user_id': user_id, 'email': user_email},
                    namespace='/'
                )
        except Exception as e:
            print(f"[USER_CONTROLLER] Error broadcasting user deletion: {e}")

        # Send sync_users command to all desktops
        try:
            remote_commands_service.send_user_sync_command(
                action='user_deleted',
                params={'user': {'id': user_id, 'email': user_email}},
                user_email=actor_email
            )
        except Exception as e:
            print(f"[USER_CONTROLLER] Error sending sync_users command: {e}")

        return {'message': 'User deleted'}, 200
    
    @staticmethod
    def change_password(user_id, current_password, new_password):
        audit_service = get_audit_logging_service()
        actor_email = g.user.get('email') if hasattr(g, 'user') else None
        
        user = User.query.get(user_id)
        if not user:
            return {'error': _USER_NOT_FOUND}, 404
        
        if not user.check_password(current_password):
            # Log failed password change attempt
            audit_service.log_event(
                event_type='user_password_change_failed',
                action='update',
                resource_type='user',
                resource_id=str(user_id),
                resource_name=user.email,
                actor_email=actor_email,
                status='failure',
                error_message='Current password is incorrect',
                severity='warning'
            )
            return {'error': 'Current password is incorrect'}, 401
        
        user.set_password(new_password)
        db.session.commit()
        
        # Log password change
        audit_service.log_user_password_changed(
            user_id=user_id,
            user_email=user.email,
            actor_email=actor_email
        )

        # Sync updated password hash to SQLite
        sync_service.sync_user_to_sqlite({
            'email': user.email,
            'name': user.name,
            'password_hash': user.password_hash,
            'role': user.role,
            'is_active': user.is_active
        })
        
        return {'message': 'Password changed successfully'}, 200
