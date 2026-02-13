"""
Bank-Grade AI Report Designer — Flask Application Factory
"""

import os
from flask import Flask
from flask_cors import CORS
from backend.config.settings import Config


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY

    # CORS configuration
    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}},
         supports_credentials=True)

    # Ensure reports directory exists
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)

    # Register blueprints
    from backend.routes.auth_routes import auth_bp
    from backend.routes.chat_routes import chat_bp
    from backend.routes.report_routes import report_bp
    from backend.routes.audit_routes import audit_bp
    from backend.routes.schema_routes import schema_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(schema_bp)

    # Health check
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return {"status": "healthy", "service": "Bank-Grade Report Designer"}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
