from flask import Blueprint, request, jsonify
from app.controllers.parameter_controller import ParameterController
from app.middleware.auth_middleware import token_required, etag_response
from app.services.cache_service import cache_get, cache_set, cache_delete_pattern

parameter_bp = Blueprint('parameters', __name__, url_prefix='/api/parameters')

_CACHE_TTL = 60  # seconds


@parameter_bp.route('', methods=['GET'])
@token_required
def get_parameters():
    cache_key = 'parameters:all'
    cached = cache_get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        return etag_response(resp)

    result, status = ParameterController.get_all_parameters()
    if status == 200:
        cache_set(cache_key, result, ttl=_CACHE_TTL)
    resp = jsonify(result)
    return etag_response(resp) if status == 200 else (resp, status)


@parameter_bp.route('', methods=['POST'])
@token_required
def create_parameter():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result, status = ParameterController.create_parameter(data)
    if status == 201:
        cache_delete_pattern('parameters:*')
    return jsonify(result), status


@parameter_bp.route('/<int:param_id>', methods=['GET'])
@token_required
def get_parameter(param_id):
    cache_key = f'parameters:{param_id}'
    cached = cache_get(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        return etag_response(resp)

    result, status = ParameterController.get_parameter_by_id(param_id)
    if status == 200:
        cache_set(cache_key, result, ttl=_CACHE_TTL)
    resp = jsonify(result)
    return etag_response(resp) if status == 200 else (resp, status)


@parameter_bp.route('/<int:param_id>', methods=['PUT'])
@token_required
def update_parameter(param_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    result, status = ParameterController.update_parameter(param_id, data)
    if status == 200:
        cache_delete_pattern('parameters:*')
    return jsonify(result), status


@parameter_bp.route('/<int:param_id>', methods=['DELETE'])
@token_required
def delete_parameter(param_id):
    result, status = ParameterController.delete_parameter(param_id)
    if status == 200:
        cache_delete_pattern('parameters:*')
    return jsonify(result), status
