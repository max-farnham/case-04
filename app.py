from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line
import hashlib

def hash_value(value: str) -> str:
    """Return SHA-256 hash of the input string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def generate_submission_id(email: str) -> str:
    """Generate a stable submission_id from email + current UTC date-hour."""
    from datetime import datetime
    date_hour = datetime.utcnow().strftime("%Y%m%d%H")
    return hashlib.sha256((email + date_hour).encode("utf-8")).hexdigest()

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})

@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })


@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    # Convert to dict for manipulation
    record_data = submission.dict()

    # Hash PII
    record_data["email"] = hash_value(record_data["email"])
    record_data["age"] = hash_value(str(record_data["age"]))

    # Generate submission_id if missing
    if not record_data.get("submission_id"):
        record_data["submission_id"] = generate_submission_id(record_data["email"])

    # Add server-enriched fields
    record_data["received_at"] = datetime.now(timezone.utc)
    record_data["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    record_data["user_agent"] = request.headers.get("User-Agent", record_data.get("user_agent"))

    # Save using your existing helper
    append_json_line(record_data)

    return jsonify({"status": "ok"}), 201

if __name__ == "__main__":
    app.run(port=0, debug=True)
