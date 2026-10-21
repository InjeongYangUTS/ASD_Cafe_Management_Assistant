
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import MULTI_AGENT_HOST, MULTI_AGENT_PORT
from workflow import (
    start_workflow,
    get_workflow,
    submit_human_review
)

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    """Check whether the Multi-Agent Server is running."""
    return jsonify({
        "status": "ok",
        "service": "multi-agent-server"
    }), 200


@app.route("/workflows", methods=["POST"])
def create_workflow():
    """Start a Planner → Worker → Reviewer workflow."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A JSON object is required."
        }), 400

    task = data.get("task")
    evidence = data.get("evidence", {})

    if not isinstance(task, str) or not task.strip():
        return jsonify({
            "error": "A non-empty task is required."
        }), 400

    if not isinstance(evidence, dict):
        return jsonify({
            "error": "Evidence must be a JSON object."
        }), 400

    try:
        result = start_workflow(task, evidence)

        return jsonify(result), 201

    except Exception:
        app.logger.exception("Multi-Agent workflow failed")

        return jsonify({
            "error": "Unable to complete the workflow."
        }), 500


@app.route("/workflows/<workflow_id>", methods=["GET"])
def workflow_details(workflow_id):
    """Retrieve workflow results and audit history."""

    result = get_workflow(workflow_id)

    if result is None:
        return jsonify({
            "error": "Workflow not found."
        }), 404

    return jsonify(result), 200


@app.route(
    "/workflows/<workflow_id>/human-review",
    methods=["POST"]
)
def human_review(workflow_id):
    """Submit a human approval, correction or rejection."""

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A JSON object is required."
        }), 400

    decision = data.get("decision")
    comments = data.get("comments", "")

    try:
        result = submit_human_review(
            workflow_id,
            decision,
            comments
        )

        return jsonify(result), 200

    except LookupError:
        return jsonify({
            "error": "Workflow not found."
        }), 404

    except ValueError as error:
        if str(error) in (
            "Decision must be approve, correct, reject or partial_accept.",
            "Comments must be text.",
            "Workflow is not awaiting human review.",
            "Correction comments are required."
        ):
            return jsonify({
                "error": str(error)
            }), 400

        app.logger.exception("Human Review agent validation failed")

        return jsonify({
            "error": "Unable to complete the Human Review."
        }), 500

    except Exception:
        app.logger.exception("Human Review workflow failed")

        return jsonify({
            "error": "Unable to complete the Human Review."
        }), 500


if __name__ == "__main__":
    app.run(
        host=MULTI_AGENT_HOST,
        port=MULTI_AGENT_PORT,
        debug=False
    )
