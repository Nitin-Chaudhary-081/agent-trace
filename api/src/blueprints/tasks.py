"""Task endpoints — submit an agent run, list runs."""

from flask import Blueprint, current_app, jsonify, request

from src.errors import ValidationError

bp = Blueprint("tasks", __name__)

TASK_TYPES = ("research_and_email", "inbox_summarize", "data_lookup_report")


@bp.post("")
def submit_task():
    payload = request.get_json(silent=True) or {}
    task = (payload.get("task") or "").strip()
    task_type = (payload.get("task_type") or "").strip()

    if not task:
        raise ValidationError("task is required")
    if task_type and task_type not in TASK_TYPES:
        raise ValidationError(f"unsupported task_type: {task_type}")

    runtime = current_app.config["runtime"]
    run_id = runtime.submit(task, task_type or "research_and_email")

    return jsonify({"run_id": run_id, "status": "accepted"}), 202


@bp.get("")
def list_runs():
    runtime = current_app.config["runtime"]
    rows = runtime.trajectory.all_runs()
    return jsonify({"runs": rows}), 200
