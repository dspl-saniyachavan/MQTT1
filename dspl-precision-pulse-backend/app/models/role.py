"""
Role model for role-based access control
"""
from app.models import db
from datetime import datetime, timezone, timezone

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, default=False)  # System roles cannot be deleted
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    permissions = db.relationship('Permission', backref='role', lazy=True, cascade='all, delete-orphan')
    users = db.relationship('User', backref='role_obj', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'permissions': [p.to_dict() for p in self.permissions],
            'created_at': self.created_at.isoformat()
        }
    
    def has_permission(self, resource: str, action: str) -> bool:
        """Check if role has permission for resource action"""
        for perm in self.permissions:
            if perm.resource == resource and perm.action == action and perm.allowed:
                return True
        return False
