"""
Audit routes — admin-only audit log viewer.
"""

from flask import Blueprint, request, jsonify, g
from backend.auth.middleware import jwt_required, role_required
from backend.models.base import get_db_session
from backend.models.audit import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("/logs", methods=["GET"])
@jwt_required
@role_required("admin")
def get_audit_logs():
    """Get audit logs (admin only). Supports pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)  # Cap at 100

    action_filter = request.args.get("action")

    session = get_db_session()
    try:
        query = session.query(AuditLog).order_by(AuditLog.created_at.desc())

        if action_filter:
            query = query.filter(AuditLog.action == action_filter)

        total = query.count()
        logs = query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "logs": [log.to_dict() for log in logs],
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    finally:
        session.close()


@audit_bp.route("/login-history", methods=["GET"])
@jwt_required
def get_login_history():
    """Get login history (accessible by all authenticated users)."""
    session = get_db_session()
    try:
        logs = (
            session.query(AuditLog)
            .filter(AuditLog.action == "LOGIN")
            .order_by(AuditLog.created_at.desc())
            .limit(50)
            .all()
        )

        history = []
        for log in logs:
            history.append({
                "id": log.audit_id, # Added id for deletion
                "name": log.username,
                "role": log.user_role,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "status": log.status,
            })

        return jsonify(history)
    finally:
        session.close()


@audit_bp.route("/login-history/<int:log_id>", methods=["DELETE"])
@jwt_required
def delete_login_history(log_id):
    """Delete a login history record."""
    user = g.current_user
    session = get_db_session()
    try:
        # Security: only delete LOGIN entries for this user
        log_entry = session.query(AuditLog).filter(
            AuditLog.audit_id == log_id,
            AuditLog.action == "LOGIN",
            AuditLog.user_id == user["user_id"]
        ).first()

        if not log_entry:
            return jsonify({"status": "error", "message": "Log entry not found or unauthorized"}), 404

        session.delete(log_entry)
        session.commit()
        return jsonify({"status": "success", "message": "Login history entry deleted"})
    except Exception as e:
        session.rollback()
        print(f"Error deleting login history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        session.close()
