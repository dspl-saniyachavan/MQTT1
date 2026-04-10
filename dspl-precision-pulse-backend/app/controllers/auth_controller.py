from app.models.user import User
from app.models import db
from app.utils.jwt_utils import create_token
from app.services.audit_logging_service import get_audit_logging_service
from flask import jsonify, request

class AuthController:
    @staticmethod
    def login(email, password):
        audit_service = get_audit_logging_service()
        actor_ip = request.remote_addr if request else None
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            # Log failed login attempt
            audit_service.log_login_failed(
                user_email=email,
                actor_ip=actor_ip,
                error_message='Invalid credentials'
            )
            return {'error': 'Invalid credentials'}, 401
        
        if not user.is_active:
            # Log failed login for disabled account
            audit_service.log_login_failed(
                user_email=email,
                actor_ip=actor_ip,
                error_message='Account is disabled'
            )
            return {'error': 'Account is disabled'}, 403
        
        token = create_token(user.id, user.email, user.role)
        
        # Log successful login
        audit_service.log_login_success(
            user_id=user.id,
            user_email=user.email,
            actor_ip=actor_ip
        )

        # Broadcast login event so web UI can show Active status
        try:
            from app import get_socketio
            sio = get_socketio()
            if sio:
                sio.emit('user_logged_in', {'email': user.email, 'user_id': user.id}, namespace='/')
        except Exception:
            pass
        
        return {
            'token': token,
            'user': user.to_dict()
        }, 200
    
    @staticmethod
    def register(email, name, password, role='user'):
        audit_service = get_audit_logging_service()
        actor_ip = request.remote_addr if request else None
        
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
                'role': user.role
            },
            actor_email=email,
            context={'registration': True}
        )
        
        token = create_token(user.id, user.email, user.role)
        return {
            'token': token,
            'user': user.to_dict()
        }, 201
