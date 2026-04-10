"""
Conflict resolution service for sync conflicts
"""
import logging
from datetime import datetime, timezone
from app.models import db
from app.models.conflict_log import ConflictLog

logger = logging.getLogger(__name__)

class ConflictResolver:
    """Detect and resolve sync conflicts"""

    # ── Pure stateless API (no DB, no app context required) ──────────────────

    @staticmethod
    def _get_timestamp(data: dict):
        """Parse updated_at from a data dict. Returns datetime or None."""
        if data is None:
            return None
        val = data.get('updated_at')
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.rstrip('Z'))
            except (ValueError, AttributeError):
                return None
        return None

    @staticmethod
    def resolve_conflict(local_data, remote_data):
        """Resolve a single conflict. Returns (resolved_dict, strategy_str)."""
        if local_data is None:
            return remote_data, 'default'
        if remote_data is None:
            return local_data, 'default'
        local_ts  = ConflictResolver._get_timestamp(local_data)
        remote_ts = ConflictResolver._get_timestamp(remote_data)
        if local_ts and remote_ts and local_ts > remote_ts:
            return local_data, 'local'
        return remote_data, 'remote'

    @staticmethod
    def resolve_conflicts_batch(conflicts: list) -> list:
        """Resolve a list of conflict dicts. Each must have 'local' and 'remote' keys."""
        results = []
        for c in conflicts:
            local  = c.get('local')
            remote = c.get('remote')
            resolved, strategy = ConflictResolver.resolve_conflict(local, remote)
            results.append({
                'id':               c.get('id'),
                'data':             resolved,
                'strategy':         strategy,
                'local_timestamp':  ConflictResolver._get_timestamp(local).isoformat() if ConflictResolver._get_timestamp(local) else None,
                'remote_timestamp': ConflictResolver._get_timestamp(remote).isoformat() if ConflictResolver._get_timestamp(remote) else None,
                'resolved_at':      datetime.now(timezone.utc).isoformat(),
            })
        return results

    @staticmethod
    def merge_field_changes(local_data: dict, remote_data: dict, field_timestamps: dict) -> dict:
        """Merge field-by-field using per-field timestamps."""
        merged = dict(local_data)
        for field, ts in field_timestamps.items():
            local_ts  = ConflictResolver._get_timestamp({'updated_at': ts.get('local')})
            remote_ts = ConflictResolver._get_timestamp({'updated_at': ts.get('remote')})
            if remote_ts and local_ts and remote_ts >= local_ts:
                merged[field] = remote_data.get(field)
            else:
                merged[field] = local_data.get(field)
        merged['conflict_resolved'] = True
        return merged

    @staticmethod
    def detect_conflicts(local_records: list, remote_records: list) -> list:
        """Return records that differ between local and remote (timestamp AND data must differ)."""
        remote_map = {r['id']: r for r in remote_records}
        conflicts = []
        for local in local_records:
            remote = remote_map.get(local['id'])
            if not remote:
                continue
            local_ts  = ConflictResolver._get_timestamp(local)
            remote_ts = ConflictResolver._get_timestamp(remote)
            # Only a conflict when timestamps differ AND data differs
            if local != remote and local_ts != remote_ts:
                conflicts.append({'id': local['id'], 'local': local, 'remote': remote})
        return conflicts

    @staticmethod
    def get_conflict_summary(conflicts: list) -> dict:
        """Summarise which side would win for each conflict."""
        local_wins = remote_wins = 0
        for c in conflicts:
            _, strategy = ConflictResolver.resolve_conflict(c.get('local'), c.get('remote'))
            if strategy == 'local':
                local_wins += 1
            else:
                remote_wins += 1
        total = len(conflicts)
        return {
            'total_conflicts':      total,
            'local_wins':           local_wins,
            'remote_wins':          remote_wins,
            'local_win_percentage':  (local_wins  / total * 100) if total else 0.0,
            'remote_win_percentage': (remote_wins / total * 100) if total else 0.0,
        }

    # ── DB-backed API (requires app context) ─────────────────────────────────

    @staticmethod
    def detect_conflict(resource_type: str, resource_id: str, backend_version: dict, desktop_version: dict):
        """Detect if versions conflict"""
        if not backend_version or not desktop_version:
            return False
        backend_ts  = backend_version.get('updated_at', '')
        desktop_ts  = desktop_version.get('updated_at', '')
        return backend_ts != desktop_ts and backend_version != desktop_version

    @staticmethod
    def log_conflict(resource_type: str, resource_id: str, backend_version: dict, desktop_version: dict):
        """Log conflict for manual resolution"""
        try:
            conflict = ConflictLog(
                resource_type=resource_type,
                resource_id=resource_id,
                backend_version=backend_version,
                desktop_version=desktop_version
            )
            db.session.add(conflict)
            db.session.commit()
            logger.warning("[CONFLICT] Logged conflict for %s:%s", resource_type, resource_id)
            return conflict.id
        except Exception as e:
            logger.error("[CONFLICT] Error logging conflict: %s", e)
            return None

    @staticmethod
    def resolve_conflict_by_id(conflict_id: int, strategy: str, resolved_version: dict = None):
        """Resolve a DB-stored conflict by ID."""
        try:
            conflict = ConflictLog.query.get(conflict_id)
            if not conflict:
                return False
            if strategy == 'backend_wins':
                conflict.resolved_version = conflict.backend_version
            elif strategy == 'desktop_wins':
                conflict.resolved_version = conflict.desktop_version
            elif strategy == 'manual' and resolved_version:
                conflict.resolved_version = resolved_version
            else:
                return False
            conflict.resolution_strategy = strategy
            conflict.resolved    = True
            conflict.resolved_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info("[CONFLICT] Resolved conflict %s with strategy %s", conflict_id, strategy)
            return True
        except Exception as e:
            logger.error("[CONFLICT] Error resolving conflict: %s", e)
            return False

    @staticmethod
    def get_unresolved_conflicts():
        return ConflictLog.query.filter_by(resolved=False).all()

    @staticmethod
    def get_conflicts_for_resource(resource_type: str, resource_id: str):
        return ConflictLog.query.filter_by(
            resource_type=resource_type, resource_id=resource_id
        ).all()


conflict_resolver = ConflictResolver()
