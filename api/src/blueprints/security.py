"""Security endpoints — adversarial attack results (Module 5).

Runs the four attacks against the app's live tool registry so detect +
remediate are exercised on real code paths.
"""

from flask import Blueprint, current_app, jsonify

from agent.security.adversarial import AdversarialSuite

bp = Blueprint("security", __name__)


@bp.get("/attacks")
def get_attacks():
    runtime = current_app.config["runtime"]
    suite = AdversarialSuite()
    suite.build(
        registry=runtime.registry,
        trajectory=runtime.trajectory,
        tmp_path="/tmp/agenttrace_security",
    )
    results = suite.run_all()
    return jsonify({"results": results}), 200