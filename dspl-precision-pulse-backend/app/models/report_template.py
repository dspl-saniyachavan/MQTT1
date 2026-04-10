from app.models import db
from datetime import datetime, timezone, timezone

class ReportTemplate(db.Model):
    __tablename__ = 'report_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    template_config = db.Column(db.JSON, nullable=False)  # chart types, filters, etc
    created_by = db.Column(db.String(120), nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'template_config': self.template_config,
            'created_by': self.created_by,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat()
        }
