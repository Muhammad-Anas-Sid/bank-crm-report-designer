"""
Report routes — generation, download, and history.
"""

import os
from flask import Blueprint, request, jsonify, send_file, g
from backend.auth.middleware import jwt_required
from backend.agents.report_planner import ReportPlanner
from backend.audit.audit_service import AuditService
from backend.config.settings import Config

report_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@report_bp.route("/generate", methods=["POST"])
@jwt_required
def generate_report():
    """Generate a report from a natural language prompt."""
    user = g.current_user
    data = request.json or {}
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"status": "error", "message": "Prompt required"}), 400

    try:
        # Build user context
        user_context = {
            "user_id": user["user_id"],
            "username": user["username"],
            "roles": user.get("roles", []),
            "full_name": user.get("full_name", user["username"]),
        }

        # Get full_name from DB
        from backend.models.base import get_db_session
        from backend.models.user import User
        session = get_db_session()
        try:
            db_user = session.query(User).filter(User.user_id == user["user_id"]).first()
            if db_user and db_user.full_name:
                user_context["full_name"] = db_user.full_name
        finally:
            session.close()

        planner = ReportPlanner()
        result = planner.generate_report(prompt, user_context)

        return jsonify(result)

    except ValueError as e:
        AuditService.log(user, "SECURITY_BLOCK", str(e), "FAILURE")
        return jsonify({"status": "error", "message": str(e)}), 400

    except Exception as e:
        print(f"Report generation error: {e}")
        AuditService.log(user, "SYSTEM_ERROR", str(e), "FAILURE")
        return jsonify({
            "status": "error",
            "message": "Sorry, I couldn't process that request. Please try a more specific banking report.",
        }), 500


@report_bp.route("/download/<filename>", methods=["GET"])
@jwt_required
def download_report(filename):
    """Download a generated report file."""
    user = g.current_user

    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"status": "error", "message": "Invalid filename"}), 400

    filepath = os.path.join(Config.REPORTS_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({"status": "error", "message": "File not found"}), 404

    AuditService.log_file_download(user, filename)

    return send_file(filepath, as_attachment=True, download_name=filename)


@report_bp.route("/history", methods=["GET"])
@jwt_required
def report_history():
    """Get report generation history for the current user."""
    user = g.current_user

    from backend.models.base import get_db_session
    from backend.models.audit import AuditLog
    session = get_db_session()
    try:
        logs = (
            session.query(AuditLog)
            .filter(
                AuditLog.user_id == user["user_id"],
                AuditLog.action == "GENERATE_REPORT",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(50)
            .all()
        )
        return jsonify([log.to_dict() for log in logs])
    finally:
        session.close()
