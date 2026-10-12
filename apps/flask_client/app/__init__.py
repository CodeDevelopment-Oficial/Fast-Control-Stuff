"""Application factory del cliente Flask (MVC)."""
from datetime import timedelta

from flask import Flask

from config import Config


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.permanent_session_lifetime = timedelta(hours=config_object.PERMANENT_SESSION_LIFETIME_HOURS)

    from app.routes.auth_routes import bp as auth_bp
    from app.routes.tool_routes import bp as tools_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tools_bp)

    return app


app = create_app()
