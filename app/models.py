from .extensions import db
from datetime import datetime

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(50), default='v1.0')
    source_file = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Respondent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    age_int = db.Column(db.Integer)
    age_bucket = db.Column(db.String(16))     # '18-24'…'60+'
    gender = db.Column(db.String(16))
    location_city = db.Column(db.String(64))
    location_province = db.Column(db.String(64))
    purchase_power = db.Column(db.String(16)) # High/Medium/Low
    ingested_at = db.Column(db.DateTime, default=datetime.utcnow)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'))
    respondent_id = db.Column(db.Integer, db.ForeignKey('respondent.id'))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    raw_row_json = db.Column(db.Text)
    hash_dedup = db.Column(db.String(64), unique=True, index=True)