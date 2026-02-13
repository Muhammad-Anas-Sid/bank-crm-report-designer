"""
Schema routes — domain and entity introspection.
"""

from flask import Blueprint, jsonify
from backend.auth.middleware import jwt_required
from backend.chat.chat_service import ChatService

schema_bp = Blueprint("schema", __name__, url_prefix="/api/schema")


@schema_bp.route("/domains", methods=["GET"])
@jwt_required
def get_domains():
    """List available banking domains."""
    return jsonify(ChatService.get_domain_info())


@schema_bp.route("/entities", methods=["GET"])
@jwt_required
def get_all_entities():
    """List all entities and their attributes from schema metadata."""
    entities = ChatService.get_schema_entities()
    return jsonify(entities)


@schema_bp.route("/entities/<domain>", methods=["GET"])
@jwt_required
def get_domain_entities(domain):
    """List entities for a specific domain."""
    domain_info = ChatService.get_domain_info()
    all_entities = ChatService.get_schema_entities()

    # Find matching domain
    target = None
    for d in domain_info["domains"]:
        if d["name"].lower().replace(" ", "_") == domain.lower().replace(" ", "_"):
            target = d
            break

    if not target:
        return jsonify({"status": "error", "message": f"Unknown domain: {domain}"}), 404

    # Get entities for this domain + shared
    result = {}
    domain_tables = target["entities"] + domain_info["shared_entities"]
    for table_name in domain_tables:
        if table_name in all_entities:
            result[table_name] = all_entities[table_name]

    return jsonify({
        "domain": target["name"],
        "entities": result,
    })
