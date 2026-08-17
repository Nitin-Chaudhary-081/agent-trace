"""Run endpoints — fetch run state, steps, JSONL export."""

import re
import uuid

from flask import Blueprint, current_app, jsonify, request, Response

from agent.services.reporter import Reporter
from src.errors import NotFoundError

bp = Blueprint("runs", __name__)

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _get_run_or_404(run_id: str):
    runtime = current_app.config["runtime"]
    run = runtime.trajectory.get_run(run_id)
    if run is None:
        raise NotFoundError("run", run_id)
    return runtime, run


def _validate_run_id(run_id: str) -> None:
    try:
        uuid.UUID(run_id)
    except ValueError as exc:
        raise NotFoundError("run", run_id) from exc


@bp.get("/<run_id>")
def get_run(run_id: str):
    _validate_run_id(run_id)
    runtime, run = _get_run_or_404(run_id)
    steps = runtime.trajectory.steps(run_id)
    deviations = Reporter(runtime.trajectory).deviations_for(run_id)
    return jsonify({"run": run, "steps": steps, "deviations": deviations}), 200


@bp.get("/<run_id>/export")
def export_run(run_id: str):
    _validate_run_id(run_id)
    runtime, _ = _get_run_or_404(run_id)
    reporter = Reporter(runtime.trajectory)
    record = reporter.export_record(run_id)
    return Response(
        record + "\n",
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={run_id}.jsonl"},
    )
