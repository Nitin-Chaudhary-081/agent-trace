"""Run endpoints — fetch run state, steps, JSONL export."""

from flask import Blueprint, current_app, jsonify, request, Response

from agent.services.reporter import Reporter
from src.errors import NotFoundError

bp = Blueprint("runs", __name__)


def _get_run_or_404(run_id: str):
    runtime = current_app.config["runtime"]
    run = runtime.trajectory.get_run(run_id)
    if run is None:
        raise NotFoundError("run", run_id)
    return runtime, run


@bp.get("/<run_id>")
def get_run(run_id: str):
    runtime, run = _get_run_or_404(run_id)
    steps = runtime.trajectory.steps(run_id)
    return jsonify({"run": run, "steps": steps}), 200


@bp.get("/<run_id>/export")
def export_run(run_id: str):
    runtime, _ = _get_run_or_404(run_id)
    reporter = Reporter(runtime.trajectory)
    record = reporter.export_record(run_id)
    return Response(
        record + "\n",
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={run_id}.jsonl"},
    )
