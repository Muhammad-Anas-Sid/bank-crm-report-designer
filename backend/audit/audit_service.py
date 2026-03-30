"""
Audit logging service — automatically logs system events to audit_logs table.
"""

import json
from datetime import datetime
from flask import request
from backend.models.base import get_db_session
from backend.models.audit import AuditLog


class AuditService:
    """Provides audit logging for all system events."""

    @staticmethod
    def log(user_context: dict, action: str, details=None, status: str = "SUCCESS"):
        """
        Log an action to the audit_logs table.

        Args:
            user_context: dict with user_id, username, roles
            action: string action name (LOGIN, GENERATE_REPORT, CHAT_MESSAGE, SQL_EXECUTION, FILE_DOWNLOAD)
            details: string or dict with additional details
            status: SUCCESS or FAILURE
        """
        if isinstance(details, dict):
            details = json.dumps(details)

        session = get_db_session()
        try:
            roles = user_context.get("roles", [])
            role_str = roles[0] if isinstance(roles, list) and roles else str(roles)

            log_entry = AuditLog(
                user_id=user_context.get("user_id"),
                username=user_context.get("username"),
                user_role=role_str,
                action=action,
                details=details,
                status=status,
                ip_address=_get_client_ip(),
                created_at=datetime.utcnow(),
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"AUDIT LOG FAILURE: {e}")
        finally:
            session.close()

    @staticmethod
    def log_login(user_context: dict, success: bool = True):
        AuditService.log(
            user_context,
            "LOGIN",
            f"Login {'successful' if success else 'failed'} for {user_context.get('username')}",
            "SUCCESS" if success else "FAILURE",
        )

    @staticmethod
    def log_report_generation(user_context: dict, prompt: str, rows: int, filename: str = None):
        details = {"prompt": prompt, "rows": rows}
        if filename:
            details["filename"] = filename
        AuditService.log(user_context, "GENERATE_REPORT", details)

    @staticmethod
    def log_chat_message(user_context: dict, session_id: int, message_preview: str):
        AuditService.log(
            user_context, "CHAT_MESSAGE",
            {"session_id": session_id, "preview": message_preview[:100]},
        )

    @staticmethod
    def log_sql_execution(user_context: dict, sql_query: str):
        AuditService.log(
            user_context, "SQL_EXECUTION",
            {"query": sql_query[:500]},
        )

    @staticmethod
    def log_file_download(user_context: dict, filename: str):
        AuditService.log(user_context, "FILE_DOWNLOAD", {"filename": filename})


def _get_client_ip():
    """Get client IP address from Flask request context."""
    try:
        return request.remote_addr
    except RuntimeError:
        return None
