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

        # Fetch session history for context-aware chat
        raw_history = ChatService.get_session_messages(session_id)
        history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in raw_history
            if msg.get("role") in ["user", "assistant"]
        ]

        planner = ReportPlanner()
        result = planner.generate_report(content, user_context, history=history)

        # Check if it's an error response
        if result.get("status") == "error":
            ai_response = result.get("message", "I couldn't process that request.")
            ChatService.add_message(session_id, "assistant", f"⚠️ {ai_response}")
            return jsonify({"status": "info", "message": ai_response})

        # Handle clarify/chat intent — LLM needs more info from the user
        if result.get("status") in ("clarify", "chat"):
            ai_response = result.get("message", "Could you be more specific about what report you need?")
            suggested = result.get("suggested_questions", [])
            if suggested:
                ai_response += "\n\nHere are some things you could try:\n"
                for q in suggested:
                    ai_response += f"• {q}\n"
            ChatService.add_message(session_id, "assistant", ai_response)
            return jsonify({"status": "info", "message": ai_response})

        # If status is anything other than "success", treat as error
        if result.get("status") != "success":
            ai_response = result.get("message") or result.get("safe_message") or "Report generation failed unexpectedly."
            ChatService.add_message(session_id, "assistant", f"⚠️ {ai_response}")
            return jsonify({"status": "error", "message": ai_response}), 500

        # ── Build AI response text (success) ──────────────────────
        report_title = result.get("report_plan", {}).get("report_title", "Report")
        insights = result.get("insights", "")
        total_rows = result.get("total_rows", 0)

        # Gather data sources used
        sources_used = result.get("sources_used", [])
        source_breakdown = result.get("source_breakdown", {})

        ai_response = (
            f"✅ **Report Generated: {report_title}**\n\n"
            f"📊 {total_rows} rows of data retrieved.\n\n"
            f"{insights}\n\n"
        )

        # Append data sources used
        if sources_used:
            ai_response += "---\n\n📂 **Data Sources Used:**\n"
            for src in sources_used:
                row_count = source_breakdown.get(src, "")
                label = src.replace("_", " ").title()
                if row_count:
                    ai_response += f"• **{label}** — {row_count} rows\n"
                else:
                    ai_response += f"• **{label}**\n"
        else:
            ai_response += "📂 **Data Sources Used:** RAG Pipeline\n"

        # Save AI response
        ChatService.add_message(
            session_id, "assistant", ai_response,
            message_metadata={
                "type": "report",
                "download_link": result.get("download_link"),
                "total_rows": total_rows,
                "sources_used": sources_used,
                "source_breakdown": source_breakdown,
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
    })


@chat_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@jwt_required
def delete_session(session_id):
    """Delete a chat session."""
    user = g.current_user
    try:
        # Check ownership: get the session first
        sessions = ChatService.get_user_sessions(user["user_id"])
        if not any(s["chat_session_id"] == session_id for s in sessions):
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        ChatService.delete_session(session_id)
        return jsonify({"status": "success", "message": "Chat session deleted"})
    except Exception as e:
        print(f"Error deleting chat session: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
