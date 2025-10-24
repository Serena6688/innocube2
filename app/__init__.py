# app/__init__.py
from flask import Flask, send_from_directory, request, jsonify, abort, current_app
from pathlib import Path
from .extensions import db
from .config import Settings
from .routes.compat import bp as compat_bp


# === 这两行：如果你已经有 routes/ingest.py，就用它；没有就暂时注释掉 ===
try:
    from .routes.ingest import bp as ingest_bp
except Exception:
    ingest_bp = None

# 可选：这些蓝图缺了也没关系，先保证能启动
def _safe_register(app, bp, prefix=None):
    if not bp:
        return
    if prefix:
        app.register_blueprint(bp, url_prefix=prefix)
    else:
        app.register_blueprint(bp)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"
UPLOAD_DIR = BASE_DIR / "uploads"

# ========= 关键：这就是上传用的“应急路由” =========
#   即使其它蓝图不工作，这个也会工作。
from werkzeug.utils import secure_filename
from .ingest.pipeline import ingest_excel

def _emergency_upload_routes(app):
    ALLOWED = {".xlsx", ".xls", ".csv"}

    @app.post("/api/upload")
    @app.post("/api/upload/")  # 兼容多余斜杠
    def _compat_upload():
        if "file" not in request.files:
            return jsonify({"error": "no file"}), 400
        f = request.files["file"]
        suffix = Path(f.filename).suffix.lower()
        if not f.filename or suffix not in ALLOWED:
            return jsonify({"error": "invalid format"}), 400

        updir = Path(current_app.config.get("UPLOAD_DIR", str(UPLOAD_DIR)))
        updir.mkdir(parents=True, exist_ok=True)
        p = updir / secure_filename(f.filename)
        f.save(p)

        try:
            rows = ingest_excel(p)  # 调用你的入库逻辑
            return jsonify({"message": "ingested", "rows": rows})
        except Exception as e:
            return jsonify({"error": f"ingest failed: {e}"}), 500
# ========= /应急路由 =========


def create_app():
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="/")
    app.config.from_object(Settings())
    app.url_map.strict_slashes = False  # 避免 308/301 重定向
    db.init_app(app)

    # 注册你已有的蓝图（缺了也不会崩）
    _safe_register(app, ingest_bp, "/api/v1/ingest")
    app.register_blueprint(compat_bp)

    # 注册应急上传路由（老前端 /api/upload 直接可用）
    _emergency_upload_routes(app)

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    # 所有 /api/* 错误都返回 JSON，避免返回 HTML 触发 “<!doctype…”
    @app.errorhandler(404)
    def _404(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found", "path": request.path}), 404
        return e

    @app.errorhandler(405)
    def _405(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "method not allowed", "path": request.path}), 405
        return e

    @app.errorhandler(413)
    def _413(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "payload too large"}), 413
        return e

    # 静态首页兜底（不要拦 /api/）
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def index(path):
        if request.path.startswith("/api/"):
            abort(404)
        target = WEB_DIR / path
        if target.exists() and target.is_file():
            return send_from_directory(WEB_DIR, path)
        return send_from_directory(WEB_DIR, "index.html")

    with app.app_context():
        db.create_all()
        UPLOAD_DIR.mkdir(exist_ok=True)
        # 打印路由（确认 /api/upload 存在）
        print("== ROUTES ==")
        for r in app.url_map.iter_rules():
            print(r)
    return app