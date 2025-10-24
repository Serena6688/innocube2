# app/routes/compat.py
# -*- coding: utf-8 -*-
from typing import Optional
from flask import Blueprint, jsonify
from sqlalchemy import func
import json

from ..extensions import db
from ..models import Survey, Respondent, Response
from .ingest import upload as new_upload

bp = Blueprint("compat", __name__)

# 购买力文案标准化（返回 Optional[str] 以兼容 3.9）
def _norm_pp(v: object) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if "较高" in s:
        return "Relatively High"
    if "较低" in s:
        return "Relatively Low"
    if "高" in s or "high" in s:
        return "High"
    if "低" in s or "low" in s:
        return "Low"
    if "中" in s or "medium" in s:
        return "Medium"
    return "Medium"

# 统一排序（柱子顺序更自然）
_ORDER = {"High": 0, "Relatively High": 1, "Medium": 2, "Relatively Low": 3, "Low": 4}

# 旧上传路径（你的前端正在用）
@bp.post("/api/upload")
@bp.post("/api/upload/")
def compat_upload():
    return new_upload()

@bp.get("/api/dashboard/stats")
def compat_stats():
    return jsonify({
        "total_surveys": db.session.query(func.count(Survey.id)).scalar() or 0,
        "total_responses": db.session.query(func.count(Response.id)).scalar() or 0,
        "total_respondents": db.session.query(func.count(Respondent.id)).scalar() or 0,
        "total_questions": 0
    })

@bp.get("/api/surveys")
def compat_surveys():
    surveys = Survey.query.order_by(Survey.created_at.desc()).all()
    return jsonify([{
        "id": s.id,
        "title": s.title,
        "version": s.version,
        "created_at": s.created_at.isoformat(),
        "question_count": 0,
        "response_count": db.session.query(func.count(Response.id)).filter_by(survey_id=s.id).scalar() or 0
    } for s in surveys])

@bp.get("/api/analytics/demographics")
def compat_demographics():
    age_rows = db.session.query(Respondent.age_bucket, func.count()) \
        .filter(Respondent.age_bucket.isnot(None)) \
        .group_by(Respondent.age_bucket).all()
    gender_rows = db.session.query(Respondent.gender, func.count()) \
        .group_by(Respondent.gender).all()
    return jsonify({
        "age_distribution": [{"age_group": r[0] or "Unknown", "count": int(r[1])} for r in age_rows],
        "gender_distribution": [{"gender": r[0] or "Unknown", "count": int(r[1])} for r in gender_rows],
    })

@bp.get("/api/analytics/brand-preferences")
def compat_brand_pref():
    """
    优先从 Respondent.purchase_power 聚合；
    若没有，再从 Response 的 JSON 字段扫描：
      - 键名模糊匹配：包含 'purchase'+'power'，或包含 '购买'/'消费' 且包含 '力'
      - 值统一标准化到 5 档（High / Relatively High / Medium / Relatively Low / Low）
    返回数组，兼容旧前端：[{ question, responses:[{brand,count}], labels, counts, items }]
    """
    def norm_pp(v):
        if v is None:
            return None
        s = str(v).strip().lower()
        if "较高" in s: return "Relatively High"
        if "较低" in s: return "Relatively Low"
        if "高" in s or "high" in s: return "High"
        if "低" in s or "low" in s: return "Low"
        if "中" in s or "medium" in s: return "Medium"
        return "Medium"

    def looks_like_pp_key(k: str) -> bool:
        """更宽的键名识别：purchase+power / 购买(消费)+力 / purchasing_power 等"""
        if not k:
            return False
        raw = str(k)
        kl = raw.lower().replace("_", "").replace("-", "").replace(" ", "")
        # 英文：同时包含 purchase 和 power
        if "purchase" in kl and "power" in kl:
            return True
        # 常见缩写
        if "purchasingpower" in kl:
            return True
        # 中文：包含 购买 或 消费，且包含 力
        if ("购买" in raw or "消费" in raw) and ("力" in raw):
            return True
        return False

    ORDER = {"High":0, "Relatively High":1, "Medium":2, "Relatively Low":3, "Low":4}

    # 1) 第一优先：Respondent.purchase_power
    items = []
    if hasattr(Respondent, "purchase_power"):
        rows = db.session.query(Respondent.purchase_power, func.count()) \
            .filter(Respondent.purchase_power.isnot(None)) \
            .group_by(Respondent.purchase_power).all()
        items = [{"label": r[0], "count": int(r[1])} for r in rows if r[0]]

    # 2) 兜底：扫 Response JSON
    if not items:
        candidate_fields = [f for f in ("answers_json", "answers", "data_json", "payload", "content", "raw_json")
                            if hasattr(Response, f)]
        if candidate_fields:
            field = getattr(Response, candidate_fields[0])
            # 只扫最近一个 survey 加速；想全量就去掉 latest_survey 这两行
            latest_survey = db.session.query(Survey.id).order_by(Survey.created_at.desc()).limit(1).scalar()
            q = db.session.query(field).filter(field.isnot(None))
            if latest_survey:
                q = q.filter(Response.survey_id == latest_survey)

            counts = {}
            for (payload,) in q:
                try:
                    data = json.loads(payload)
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                # 遍历所有键，找出“像购买力”的键
                hit = None
                for k, v in data.items():
                    if looks_like_pp_key(k):
                        hit = v
                        break
                # 兜底：常见键名（如果上面没命中）
                if hit is None:
                    for k in ("purchase_power", "purchasing_power", "购买力", "消费能力"):
                        if k in data:
                            hit = data[k]
                            break
                if hit is None:
                    continue
                lab = norm_pp(hit)
                if lab:
                    counts[lab] = counts.get(lab, 0) + 1

            items = [{"label": k, "count": v} for k, v in counts.items()]

    # 3) 标准化 & 排序
    for it in items:
        it["label"] = norm_pp(it["label"]) or "Medium"
    items = [it for it in items if it["label"] is not None]
    items.sort(key=lambda x: ORDER.get(x["label"], 999))

    labels = [it["label"] for it in items]
    counts = [it["count"] for it in items]
    legacy_responses = [{"brand": it["label"], "count": it["count"]} for it in items]

    return jsonify([{
        "question": "Purchasing Power",
        "responses": legacy_responses,   # 旧前端最常用
        "labels": labels,                # 新前端可直接用
        "counts": counts,
        "items": items
    }])