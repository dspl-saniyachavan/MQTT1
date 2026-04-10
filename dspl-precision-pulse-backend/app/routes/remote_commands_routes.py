from flask import Blueprint, jsonify, request, g
from app.middleware.auth_middleware import token_required
from app.services.remote_commands_service import remote_commands_service
from app.models.command_execution import CommandExecution, CommandAcknowledgment
from app.models import db
from datetime import datetime, timezone

remote_commands_bp = Blueprint('remote_commands', __name__, url_prefix='/api/remote-commands')

@remote_commands_bp.route('/force-sync', methods=['POST'])
@token_required
def force_sync():
    """Force sync command to remote devices"""
    data = request.get_json() or {}
    device_id = data.get('device_id')
    sync_type = data.get('sync_type', 'full')
    user = request.user
    
    result = remote_commands_service.send_force_sync(
        device_id=device_id,
        sync_type=sync_type,
        user_email=user.get('email')
    )
    
    if result['success']:
        return jsonify(result), 200
    return jsonify(result), 200

@remote_commands_bp.route('/update-config', methods=['POST'])
@token_required
def update_config():
    """Send config update command to remote devices"""
    data = request.get_json()
    user = request.user
    
    if not data or 'config' not in data:
        return jsonify({'error': 'Config data required'}), 400
    
    device_id = data.get('device_id')
    config = data.get('config')
    
    result = remote_commands_service.send_config_update(
        device_id=device_id,
        config=config,
        user_email=user.get('email')
    )
    
    if result['success']:
        return jsonify(result), 200
    return jsonify(result), 200

@remote_commands_bp.route('/custom', methods=['POST'])
@token_required
def send_custom_command():
    """Send custom command to remote devices"""
    data = request.get_json()
    user = request.user
    
    if not data or 'command_type' not in data:
        return jsonify({'error': 'Command type required'}), 400
    
    command_type = data.get('command_type')
    device_id = data.get('device_id')
    params = data.get('params', {})
    
    result = remote_commands_service.send_custom_command(
        command_type=command_type,
        device_id=device_id,
        params=params,
        user_email=user.get('email')
    )
    
    if result['success']:
        return jsonify(result), 200
    return jsonify(result), 200

@remote_commands_bp.route('/status', methods=['GET'])
@token_required
def get_command_status():
    """Get status of remote commands"""
    command_id = request.args.get('command_id')
    device_id = request.args.get('device_id')
    
    result = remote_commands_service.get_command_status(command_id, device_id)
    return jsonify(result), 200

@remote_commands_bp.route('/acknowledgment', methods=['POST'])
def handle_acknowledgment():
    """Handle command acknowledgment from device (no auth required for MQTT bridge)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    command_id = data.get('command_id')
    device_id = data.get('device_id')
    ack_type = data.get('ack_type')
    status = data.get('status')
    message = data.get('message')
    result_data = data.get('result_data')
    
    if not all([command_id, device_id, ack_type, status]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    result = remote_commands_service.handle_command_acknowledgment(
        command_id=command_id,
        device_id=device_id,
        ack_type=ack_type,
        status=status,
        message=message,
        result_data=result_data
    )
    
    if result['success']:
        return jsonify(result), 200
    return jsonify(result), 500

@remote_commands_bp.route('/list', methods=['GET'])
@token_required
def list_commands():
    """List all commands with optional filtering"""
    device_id = request.args.get('device_id')
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)
    
    try:
        query = CommandExecution.query
        
        if device_id:
            query = query.filter_by(device_id=device_id)
        
        if status:
            query = query.filter_by(status=status)
        
        commands = query.order_by(CommandExecution.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'commands': [cmd.to_dict() for cmd in commands],
            'count': len(commands)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@remote_commands_bp.route('/<command_id>/details', methods=['GET'])
@token_required
def get_command_details(command_id):
    """Get detailed information about a command"""
    try:
        cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
        
        if not cmd_exec:
            return jsonify({'error': 'Command not found'}), 404
        
        acks = CommandAcknowledgment.query.filter_by(command_id=command_id).all()
        
        result = cmd_exec.to_dict()
        result['acknowledgments'] = [ack.to_dict() for ack in acks]
        result['ack_count'] = len(acks)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@remote_commands_bp.route('/<command_id>/retry', methods=['POST'])
@token_required
def retry_command(command_id):
    """Retry a failed command"""
    try:
        cmd_exec = CommandExecution.query.filter_by(command_id=command_id).first()
        
        if not cmd_exec:
            return jsonify({'error': 'Command not found'}), 404
        
        if cmd_exec.status not in ['failed', 'timeout']:
            return jsonify({'error': 'Can only retry failed or timed out commands'}), 400
        
        if cmd_exec.retry_count >= cmd_exec.max_retries:
            return jsonify({'error': 'Max retries exceeded'}), 400
        
        # Resend command
        topic = f'precisionpulse/commands/{cmd_exec.device_id}/{cmd_exec.command_type}' if cmd_exec.device_id else f'precisionpulse/commands/broadcast/{cmd_exec.command_type}'
        
        from app.services.mqtt_publisher import get_mqtt_publisher
        publisher = get_mqtt_publisher()
        success = publisher._publish(topic, cmd_exec.payload)
        
        if success:
            cmd_exec.retry_count += 1
            cmd_exec.status = 'sent'
            cmd_exec.delivery_status = 'sent'
            cmd_exec.sent_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Command retried',
                'retry_count': cmd_exec.retry_count
            }), 200
        else:
            return jsonify({'error': 'Failed to resend command'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@remote_commands_bp.route('/stats', methods=['GET'])
@token_required
def get_command_stats():
    """Get command execution statistics"""
    try:
        from sqlalchemy import func
        
        total = CommandExecution.query.count()
        completed = CommandExecution.query.filter_by(status='completed').count()
        failed = CommandExecution.query.filter_by(status='failed').count()
        pending = CommandExecution.query.filter_by(status='pending').count()
        sent = CommandExecution.query.filter_by(status='sent').count()
        
        by_type = db.session.query(
            CommandExecution.command_type,
            func.count(CommandExecution.id)
        ).group_by(CommandExecution.command_type).all()
        
        by_device = db.session.query(
            CommandExecution.device_id,
            func.count(CommandExecution.id)
        ).group_by(CommandExecution.device_id).all()
        
        return jsonify({
            'total': total,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'sent': sent,
            'by_type': {cmd_type: count for cmd_type, count in by_type},
            'by_device': {device_id or 'broadcast': count for device_id, count in by_device}
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
