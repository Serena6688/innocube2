from flask import Blueprint
bp = Blueprint("export", __name__)

@bp.get("/csv")
def export_csv():
    return {"error":"not implemented"}, 501