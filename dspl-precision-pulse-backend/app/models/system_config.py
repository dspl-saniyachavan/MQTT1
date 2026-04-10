from app.models import db
from datetime import datetime, timezone

class SystemConfig(db.Model):
    """System configuration with version tracking and field-level encryption for sensitive values."""
    __tablename__ = 'system_config'

    id          = db.Column(db.Integer, primary_key=True)
    key         = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value       = db.Column(db.Text, nullable=False)          # may be 'enc:<token>' for sensitive keys
    description = db.Column(db.String(255))
    category    = db.Column(db.String(50), default='general', index=True)
    data_type   = db.Column(db.String(20), default='string')  # string | integer | boolean | json
    is_sensitive = db.Column(db.Boolean, default=False)
    version     = db.Column(db.Integer, default=1)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    updated_by  = db.Column(db.String(100))

    __table_args__ = (
        db.Index('idx_config_category', 'category'),
        db.Index('idx_config_key', 'key'),
    )

    # ── Encryption helpers ───────────────────────────────────────────────────────────────

    def set_value(self, plaintext: str) -> None:
        """Store value, encrypting it if is_sensitive=True."""
        if self.is_sensitive:
            try:
                from app.utils.encryption import encrypt_field
                self.value = encrypt_field(plaintext)
            except Exception:
                self.value = plaintext  # fallback: store plaintext if encryption fails
        else:
            self.value = plaintext

    def get_value(self) -> str:
        """Return decrypted value for sensitive fields, raw value otherwise."""
        if self.is_sensitive:
            try:
                from app.utils.encryption import decrypt_field
                return decrypt_field(self.value)
            except Exception:
                return self.value  # fallback: return as-is
        return self.value

    # ── Serialisation ───────────────────────────────────────────────────────────────────

    def to_dict(self):
        """Sensitive values are masked in API responses; never expose raw ciphertext."""
        return {
            'id':           self.id,
            'key':          self.key,
            'value':        '***' if self.is_sensitive else self.value,
            'description':  self.description,
            'category':     self.category,
            'data_type':    self.data_type,
            'is_sensitive': self.is_sensitive,
            'version':      self.version,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
            'updated_at':   self.updated_at.isoformat() if self.updated_at else None,
            'updated_by':   self.updated_by,
        }

    def get_typed_value(self):
        """Return decrypted value with proper type conversion."""
        raw = self.get_value()
        if self.data_type == 'integer':
            return int(raw)
        if self.data_type == 'boolean':
            return raw.lower() in ('true', '1', 'yes')
        if self.data_type == 'json':
            import json
            return json.loads(raw)
        return raw
