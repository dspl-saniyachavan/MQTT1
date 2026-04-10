"""
MQTT Sync Service — handles user and parameter sync messages received via MQTT.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MQTTSyncService:
    """Process MQTT sync payloads and apply them to the PostgreSQL database."""

    def __init__(self, app=None):
        self.app = app

    # ── User sync ─────────────────────────────────────────────────────────────

    def sync_user(self, data: dict):
        """Apply a user sync payload (create / update / delete)."""
        try:
            action    = data.get('action')
            user_data = data.get('user')
            if not user_data:
                logger.warning("[MQTT_SYNC] sync_user: missing 'user' key")
                return

            from app.models.user import User
            from app.models import db

            if action == 'create':
                email = user_data.get('email')
                if not email:
                    logger.warning("[MQTT_SYNC] sync_user create: missing email")
                    return
                if User.query.filter_by(email=email).first():
                    logger.info("[MQTT_SYNC] sync_user create: duplicate email %s ignored", email)
                    return
                import bcrypt
                pw_hash = user_data.get('password_hash', bcrypt.hashpw(b'changeme', bcrypt.gensalt()).decode())
                user = User(
                    email=email,
                    name=user_data.get('name', ''),
                    password_hash=pw_hash,
                    role=user_data.get('account_type') or user_data.get('role', 'user'),
                    is_active=user_data.get('is_active', True),
                )
                db.session.add(user)
                db.session.commit()
                logger.info("[MQTT_SYNC] Created user %s", email)

            elif action == 'update':
                email = user_data.get('email')
                if not email:
                    return
                user = User.query.filter_by(email=email).first()
                if not user:
                    logger.warning("[MQTT_SYNC] sync_user update: user %s not found", email)
                    return
                if 'name' in user_data:
                    user.name = user_data['name']
                if 'account_type' in user_data:
                    user.role = user_data['account_type']
                elif 'role' in user_data:
                    user.role = user_data['role']
                if 'is_active' in user_data:
                    user.is_active = user_data['is_active']
                if 'password_hash' in user_data:
                    user.password_hash = user_data['password_hash']
                user.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info("[MQTT_SYNC] Updated user %s", email)

            elif action == 'delete':
                email = user_data.get('email')
                if not email:
                    return
                user = User.query.filter_by(email=email).first()
                if user:
                    db.session.delete(user)
                    db.session.commit()
                    logger.info("[MQTT_SYNC] Deleted user %s", email)

            else:
                logger.warning("[MQTT_SYNC] sync_user: unknown action '%s'", action)

        except Exception as exc:
            logger.error("[MQTT_SYNC] sync_user error: %s", exc)
            try:
                from app.models import db
                db.session.rollback()
            except Exception:
                pass

    # ── Parameter sync ────────────────────────────────────────────────────────

    def sync_parameter(self, data: dict):
        """Apply a parameter sync payload (create / update / delete)."""
        try:
            action     = data.get('action')
            param_data = data.get('parameter')
            if not param_data:
                logger.warning("[MQTT_SYNC] sync_parameter: missing 'parameter' key")
                return

            from app.models.parameter import Parameter
            from app.models import db

            if action == 'create':
                name = param_data.get('name')
                if not name:
                    logger.warning("[MQTT_SYNC] sync_parameter create: missing name")
                    return
                if Parameter.query.filter_by(name=name).first():
                    logger.info("[MQTT_SYNC] sync_parameter create: duplicate name '%s' ignored", name)
                    return
                param = Parameter(
                    name=name,
                    unit=param_data.get('unit', ''),
                    description=param_data.get('description', ''),
                    enabled=param_data.get('enabled', True),
                )
                db.session.add(param)
                db.session.commit()
                logger.info("[MQTT_SYNC] Created parameter '%s'", name)

            elif action == 'update':
                param_id = param_data.get('id')
                name     = param_data.get('name')
                param    = None
                if param_id:
                    param = Parameter.query.get(param_id)
                if param is None and name:
                    param = Parameter.query.filter_by(name=name).first()
                if param is None:
                    # Create if not found
                    if not name:
                        return
                    param = Parameter(
                        name=name,
                        unit=param_data.get('unit', ''),
                        description=param_data.get('description', ''),
                        enabled=param_data.get('enabled', True),
                    )
                    db.session.add(param)
                    db.session.commit()
                    logger.info("[MQTT_SYNC] Created parameter '%s' (upsert)", name)
                    return
                if 'name'        in param_data: param.name        = param_data['name']
                if 'unit'        in param_data: param.unit        = param_data['unit']
                if 'description' in param_data: param.description = param_data['description']
                if 'enabled'     in param_data: param.enabled     = bool(param_data['enabled'])
                param.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info("[MQTT_SYNC] Updated parameter id=%s", param.id)

            elif action == 'delete':
                param_id = param_data.get('id')
                if not param_id:
                    return
                param = Parameter.query.get(param_id)
                if param:
                    db.session.delete(param)
                    db.session.commit()
                    logger.info("[MQTT_SYNC] Deleted parameter id=%s", param_id)

            else:
                logger.warning("[MQTT_SYNC] sync_parameter: unknown action '%s'", action)

        except Exception as exc:
            logger.error("[MQTT_SYNC] sync_parameter error: %s", exc)
            try:
                from app.models import db
                db.session.rollback()
            except Exception:
                pass
