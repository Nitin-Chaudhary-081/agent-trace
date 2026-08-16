"""Application factory — Flask, CodeSentinel pattern."""

from flask import Flask
from flask_cors import CORS

from src.blueprints import memory, runs, security, tasks
from src.config import settings
from src.errors import ApiError, to_envelope
from src.runtime import AgentRuntime

__version__ = "0.1.0"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DEBUG"] = settings.debug

    CORS(app, origins=settings.cors_origins, supports_credentials=True)

    app.config["runtime"] = AgentRuntime(
        database_path=settings.database_path,
        memory_path=settings.memory_path,
        max_steps=settings.max_steps,
        tool_timeout_s=settings.tool_timeout_s,
    )

    app.register_blueprint(tasks.bp, url_prefix="/api/v1/tasks")
    app.register_blueprint(runs.bp, url_prefix="/api/v1/runs")
    app.register_blueprint(memory.bp, url_prefix="/api/v1/memory")
    app.register_blueprint(security.bp, url_prefix="/api/v1/security")

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return to_envelope(exc), exc.status_code

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        app.logger.exception("unhandled error", exc_info=exc)
        return (
            {"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
            500,
        )

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
