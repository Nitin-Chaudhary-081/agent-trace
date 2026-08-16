"""Memory endpoints — live MEMORY.md sections."""

from flask import Blueprint, current_app, jsonify

bp = Blueprint("memory", __name__)


@bp.get("")
def get_memory():
    runtime = current_app.config["runtime"]
    sections = runtime.memory.read()
    return jsonify({"sections": sections}), 200