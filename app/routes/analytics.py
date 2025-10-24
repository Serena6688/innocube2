from flask import Blueprint, request
from sqlalchemy import func
from ..extensions import db
from ..models import Respondent

bp = Blueprint("analytics", __name__)

def apply_filters(q):
    age = request.args.get("age_bucket")
    pp  = request.args.get("purchase_power")
    prov= request.args.get("province")
    if age: q = q.filter(Respondent.age_bucket.in_(age.split(",")))
    if pp:  q = q.filter(Respondent.purchase_power.in_(pp.split(",")))
    if prov:q = q.filter(Respondent.location_province.in_(prov.split(",")))
    return q

@bp.get("/age")
def age():
    q = db.session.query(Respondent.age_bucket, func.count()).filter(Respondent.age_bucket.isnot(None))
    q = apply_filters(q).group_by(Respondent.age_bucket)
    return [{"age_bucket": b or "Unknown", "count": c} for b,c in q.all()]

@bp.get("/purchase_power")
def purchase_power():
    q = db.session.query(Respondent.purchase_power, func.count()).filter(Respondent.purchase_power.isnot(None))
    q = apply_filters(q).group_by(Respondent.purchase_power)
    return [{"level": lvl or "Unknown", "count": c} for lvl,c in q.all()]