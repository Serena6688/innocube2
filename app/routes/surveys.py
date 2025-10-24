from flask import Blueprint
from ..models import Survey

bp = Blueprint("surveys", __name__)

@bp.get("/")
def list_surveys():
    return [{
        "id": s.id, "title": s.title, "version": s.version,
        "created_at": s.created_at.isoformat()
    } for s in Survey.query.order_by(Survey.created_at.desc()).all()]