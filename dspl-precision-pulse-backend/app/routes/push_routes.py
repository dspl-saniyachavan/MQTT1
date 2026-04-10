import os
from flask import Blueprint, request, jsonify
from app.middleware.auth_middleware import token_required
from app.models.push_subscription import PushSubscription
from app.models import db
import json

push_bp = Blueprint('push', __name__, url_prefix='/api/push')


@push_bp.route('/vapid-public-key', methods=['GET'])
def get_vapid_public_key():
    key = os.environ.get('VAPID_PUBLIC_KEY', '')
    return jsonify({'publicKey': key}), 200


@push_bp.route('/subscribe', methods=['POST'])
@token_required
def subscribe():
    data = request.get_json() or {}
    sub_json = json.dumps(data.get('subscription', data))
    existing = PushSubscription.query.filter_by(subscription_json=sub_json).first()
    if not existing:
        sub = PushSubscription(subscription_json=sub_json)
        db.session.add(sub)
        db.session.commit()
    return jsonify({'ok': True}), 200


@push_bp.route('/unsubscribe', methods=['POST'])
@token_required
def unsubscribe():
    data = request.get_json() or {}
    sub_json = json.dumps(data.get('subscription', data))
    sub = PushSubscription.query.filter_by(subscription_json=sub_json).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
    return jsonify({'ok': True}), 200
