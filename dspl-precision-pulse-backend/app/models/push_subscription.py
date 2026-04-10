from app.models import db
from datetime import datetime, timezone


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, nullable=True)
    subscription_json = db.Column(db.Text, nullable=False, unique=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
