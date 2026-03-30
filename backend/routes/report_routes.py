"""
Report routes — generation, download, and history.
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, g
from werkzeug.utils import secure_filename
from backend.auth.middleware import jwt_required
from backend.agents.report_planner import ReportPlanner
from backend.audit.audit_service import AuditService
from backend.config.settings import Config

logger = logging.getLogger(__name__)
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
        logger.error(f"Report generation error: {e}")
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

    is_preview = request.args.get("preview") == "true"
    return send_file(filepath, as_attachment=not is_preview, download_name=filename)


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


@report_bp.route("/delete/<path:filename>", methods=["DELETE"])
@jwt_required
def delete_report(filename):
    """Delete a report file and its history entry."""
    user = g.current_user
    try:
        if not user:
            return jsonify({"error": "Unauthorized"}), 401

        # Use secure_filename to be safe
        safe_filename = secure_filename(filename)
        filepath = os.path.join(Config.REPORTS_DIR, safe_filename)

        # Delete physical file
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted report file: {filepath}")
        else:
            logger.warning(f"Report file not found for deletion: {filepath}")

        # Delete from audit logs
        from backend.models.base import get_db_session
        from backend.models.audit import AuditLog
        session = get_db_session()
        try:
            # Note: The filename in download_link might have prefixes or be different, 
            # but usually AuditLog stores it in details or a dedicated field.
            # Looking at ReportPlanner, it logs: "Report generated: filename"
            # We filter by action and user_id to be safe.
            logs = session.query(AuditLog).filter(
                AuditLog.user_id == user["user_id"],
                AuditLog.action == "GENERATE_REPORT"
            ).all()
            
            deleted_count = 0
            for log in logs:
                # Assuming the filename is stored in details or we can match it
                if safe_filename in str(log.details):
                    session.delete(log)
                    deleted_count += 1
            
            session.commit()
            logger.info(f"Deleted {deleted_count} audit log entries for report: {safe_filename}")
        finally:
            session.close()

        return jsonify({
            "status": "success",
            "message": f"Successfully deleted report {safe_filename}"
        }), 200

    except Exception as e:
        logger.error(f"Error deleting report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
