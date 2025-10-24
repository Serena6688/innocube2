from flask import Blueprint, current_app, request, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
from ..ingest.pipeline import ingest_excel

bp = Blueprint("ingest", __name__)
ALLOWED = {".xlsx", ".xls", ".csv"}

@bp.post("/upload")
def upload():
    # 一定返回 JSON
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    suffix = Path(f.filename).suffix.lower()
    if not f.filename or suffix not in ALLOWED:
        return jsonify({"error": "invalid format"}), 400

    updir = Path(current_app.config["UPLOAD_DIR"])
    updir.mkdir(parents=True, exist_ok=True)
    p = updir / secure_filename(f.filename)
    f.save(p)

    try:
        rows = ingest_excel(p)
        return jsonify({"message": "ingested", "rows": rows})
    except Exception as e:
        return jsonify({"error": f"ingest failed: {e}"}), 500