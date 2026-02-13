"""
Chat routes — session management and AI messaging.
"""

from flask import Blueprint, request, jsonify, g
from backend.auth.middleware import jwt_required
from backend.chat.chat_service import ChatService
from backend.agents.report_planner import ReportPlanner
from backend.audit.audit_service import AuditService

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("/sessions", methods=["POST"])
@jwt_required
def create_session():
    """Create a new chat session for the current user."""
    user = g.current_user
    data = request.json or {}
    title = data.get("title", "New Chat")

    chat_session = ChatService.create_session(user["user_id"], title)

    # Add AI greeting as first message
    greeting = ChatService.get_greeting(user["username"])
    domain_info = ChatService.get_domain_info()

    greeting_content = (
        f"{greeting}\n\n"
        f"Available Domains:\n"
        f"• Card Management System\n"
        f"• Transaction Management System\n\n"
        f"Just describe the report you need, and I'll generate it for you."
    )

    ChatService.add_message(
        chat_session["chat_session_id"],
        "assistant",
        greeting_content,
        message_metadata={"type": "greeting", "domains": domain_info},
    )

    return jsonify({"status": "success", "session": chat_session}), 201


@chat_bp.route("/sessions", methods=["GET"])
@jwt_required
def list_sessions():
    """List all chat sessions for the current user."""
    user = g.current_user
    sessions = ChatService.get_user_sessions(user["user_id"])
    return jsonify(sessions)


@chat_bp.route("/sessions/<int:session_id>/messages", methods=["GET"])
@jwt_required
def get_messages(session_id):
    """Get all messages in a chat session."""
    messages = ChatService.get_session_messages(session_id)
    return jsonify(messages)


@chat_bp.route("/messages", methods=["POST"])
@jwt_required
def send_message():
    """
    Send a user message and get AI response.
    This triggers the full report generation pipeline if the message is a report request.
    """
    user = g.current_user
    data = request.json or {}
    session_id = data.get("session_id")
    content = data.get("content", "").strip()

    if not session_id or not content:
        return jsonify({"status": "error", "message": "session_id and content required"}), 400

    # Save user message
    ChatService.add_message(session_id, "user", content)
    AuditService.log_chat_message(user, session_id, content)

    # Process through report pipeline
    try:
        user_context = {
            "user_id": user["user_id"],
            "username": user["username"],
            "roles": user.get("roles", []),
            "full_name": user.get("full_name", user["username"]),
        }

        # Get full_name from DB if not in token
        if user_context["full_name"] == user["username"]:
            from backend.models.base import get_db_session
            from backend.models.user import User
            db_session = get_db_session()
            try:
                db_user = db_session.query(User).filter(User.user_id == user["user_id"]).first()
                if db_user and db_user.full_name:
                    user_context["full_name"] = db_user.full_name
            finally:
                db_session.close()

        planner = ReportPlanner()
        result = planner.generate_report(content, user_context)

        # Check if it's an error/greeting response
        if result.get("status") == "error":
            ai_response = result.get("message", "I couldn't process that request.")
            ChatService.add_message(session_id, "assistant", ai_response)
            return jsonify({"status": "info", "message": ai_response})

        # Build AI response text
        report_title = result.get("report_plan", {}).get("report_title", "Report")
        insights = result.get("insights", "")
        total_rows = result.get("total_rows", 0)

        ai_response = (
            f"✅ **Report Generated: {report_title}**\n\n"
            f"📊 {total_rows} rows of data retrieved.\n\n"
            f"{insights}"
        )

        # Save AI response
        ChatService.add_message(
            session_id, "assistant", ai_response,
            message_metadata={
                "type": "report",
                "download_link": result.get("download_link"),
                "total_rows": total_rows,
            },
        )

        # Update session title based on report
        ChatService.update_session_title(session_id, report_title)

        return jsonify({
            "status": "success",
            "message": ai_response,
            "report": result,
        })

    except ValueError as e:
        error_msg = str(e)
        ChatService.add_message(session_id, "assistant", f"⚠️ {error_msg}")
        AuditService.log(user, "REPORT_ERROR", error_msg, "FAILURE")
        return jsonify({"status": "error", "message": error_msg}), 400

    except Exception as e:
        error_msg = "Sorry, I couldn't process that request. Please try a more specific banking report."
        print(f"Chat processing error: {e}")
        ChatService.add_message(session_id, "assistant", f"⚠️ {error_msg}")
        AuditService.log(user, "SYSTEM_ERROR", str(e), "FAILURE")
        return jsonify({"status": "error", "message": error_msg}), 500


@chat_bp.route("/domains", methods=["GET"])
@jwt_required
def get_domains():
    """Get available domains and schema entities."""
    domain_info = ChatService.get_domain_info()
    entities = ChatService.get_schema_entities()
    return jsonify({
        "domains": domain_info,
        "entities": entities,
    })
