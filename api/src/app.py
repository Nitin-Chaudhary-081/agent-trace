"""Application factory — Flask, CodeSentinel pattern."""

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.blueprints import memory, runs, security, tasks
from src.config import settings
from src.errors import ApiError, to_envelope
from src.runtime import AgentRuntime

__version__ = "0.1.0"

API_PREFIX = "/api/v1"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DEBUG"] = settings.debug

    CORS(app, origins=settings.cors_origins)

    app.config["runtime"] = AgentRuntime(
        database_path=settings.database_path,
        memory_path=settings.memory_path,
        max_steps=settings.max_steps,
        tool_timeout_s=settings.tool_timeout_s,
    )

    app.register_blueprint(tasks.bp, url_prefix=f"{API_PREFIX}/tasks")
    app.register_blueprint(runs.bp, url_prefix=f"{API_PREFIX}/runs")
    app.register_blueprint(memory.bp, url_prefix=f"{API_PREFIX}/memory")
    app.register_blueprint(security.bp, url_prefix=f"{API_PREFIX}/security")

    @app.before_request
    def require_api_token():
        """Optional bearer-token auth. Enabled when AGENTTRACE_API_TOKEN is set.

        Health and CORS preflight stay open; everything else under /api/v1
        requires `Authorization: Bearer <token>`. Off by default so the local
        observer runs without config.
        """
        expected = settings.api_token
        if not expected:
            return None
        if request.method == "OPTIONS" or request.path == "/health":
            return None
        if request.path.startswith(API_PREFIX):
            header = request.headers.get("Authorization", "")
            if header != f"Bearer {expected}":
                return (
                    jsonify({"error": {"code": "UNAUTHORIZED", "message": "missing or invalid API token"}}),
                    401,
                )
        return None

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
