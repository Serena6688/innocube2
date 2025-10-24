# app/ingest/pipeline.py
# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from ..extensions import db
from ..models import Survey, Respondent, Response

ALLOWED = {".xlsx", ".xls", ".csv"}

# 中英文列名映射
COL_MAP = {
    "年龄": "age",
    "age": "age",
    "年龄段": "age_bucket",
    "age_bucket": "age_bucket",
    "性别": "gender",
    "gender": "gender",
    "城市": "city",
    "city": "city",
    "省份": "province",
    "province": "province",
    "购买力": "purchase_power",
    "消费能力": "purchase_power",
    "purchasing_power": "purchase_power",
    "purchase_power": "purchase_power",
}

def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    df.columns = [COL_MAP.get(c, c) for c in df.columns]
    return df

def _read_any(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf not in ALLOWED:
        raise ValueError(f"Unsupported file type: {suf}")
    if suf == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            return pd.read_csv(path)
    try:
        return pd.read_excel(path, engine="openpyxl")
    except Exception:
        return pd.read_excel(path)

def _parse_age_number(v: object) -> Optional[int]:
    """能转纯数字就返回 int，否则返回 None；'45-49' 这类不要转数字"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    try:
        f = float(s)
        if f.is_integer():
            return int(f)
    except Exception:
        pass
    return None

def _normalize_age_bucket(v: object) -> Optional[str]:
    """把 '45-49' / '45-49岁' / '45-49 岁段' 归一成 '45-49'；否则 None"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    s = s.replace("岁段", "").replace("岁", "").replace(" ", "")
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return f"{parts[0]}-{parts[1]}"
    return None

def _bucket_from_number(age: int) -> str:
    a = int(age)
    if a <= 24: return "18-24"
    if a <= 34: return "25-34"
    if a <= 39: return "35-39"
    if a <= 44: return "40-44"
    if a <= 49: return "45-49"
    if a <= 54: return "50-54"
    if a <= 59: return "55-59"
    return "60+"

def _normalize_purchase_power(v: object) -> Optional[str]:
    """中英混填购买力归一到 5 档；无法判断时给 Medium"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().lower()
    if "较高" in s: return "Relatively High"
    if "较低" in s: return "Relatively Low"
    if "高" in s or "high" in s: return "High"
    if "低" in s or "low" in s: return "Low"
    if "中" in s or "medium" in s: return "Medium"
    return "Medium"

def ingest_excel(path: Path) -> int:
    """
    读取 CSV/Excel → 规范列 → 生成 Survey / Respondent / Response → 返回入库记录数（行数）
    - 兼容 age 数值 / '45-49' 区间
    - 兼容 purchase_power 中英混填
    - 动态探测模型字段名（避免 invalid keyword argument）
    """
    df = _read_any(path)
    df = df.dropna(how="all")
    if df.empty:
        return 0
    df = _standardize_columns(df)

    # 新建一个 survey
    survey = Survey(title=f"Survey from {path.name}", version="v1.0")
    db.session.add(survey)
    db.session.flush()

    # 动态探测 Respondent/Response 模型字段
    has_age         = hasattr(Respondent, "age")
    has_age_int     = hasattr(Respondent, "age_int")
    has_age_bucket  = hasattr(Respondent, "age_bucket")
    has_gender      = hasattr(Respondent, "gender")
    # city/province 兼容 location_city/location_province
    has_city        = hasattr(Respondent, "city")
    has_loc_city    = hasattr(Respondent, "location_city")
    has_province    = hasattr(Respondent, "province")
    has_loc_province= hasattr(Respondent, "location_province")
    has_pp          = hasattr(Respondent, "purchase_power")

    # Response 可接收 answers 的字段候选（按优先级）
    resp_answer_fields = [f for f in (
        "answers_json", "answers", "data_json", "payload", "content", "raw_json"
    ) if hasattr(Response, f)]

    rows = 0
    for _, row in df.iterrows():
        # --- 年龄 ---
        age_num: Optional[int] = None
        age_bucket: Optional[str] = None

        if "age_bucket" in df.columns and pd.notna(row.get("age_bucket")):
            age_bucket = _normalize_age_bucket(row.get("age_bucket"))

        if "age" in df.columns and pd.notna(row.get("age")):
            maybe = _parse_age_number(row.get("age"))
            if maybe is not None:
                age_num = maybe
                if not age_bucket:
                    age_bucket = _bucket_from_number(age_num)
            else:
                if not age_bucket:
                    age_bucket = _normalize_age_bucket(row.get("age"))

        # --- 购买力 ---
        pp_std: Optional[str] = None
        if "purchase_power" in df.columns and pd.notna(row.get("purchase_power")):
            pp_std = _normalize_purchase_power(row.get("purchase_power"))

        # --- 构造 Respondent（仅传存在的字段） ---
        resp_kwargs = {}
        if has_age and age_num is not None:
            resp_kwargs["age"] = age_num
        if has_age_int and age_num is not None:
            resp_kwargs["age_int"] = age_num
        if has_age_bucket and age_bucket:
            resp_kwargs["age_bucket"] = age_bucket
        if has_gender and pd.notna(row.get("gender")):
            resp_kwargs["gender"] = str(row.get("gender")).strip()

        val_city = str(row.get("city")).strip() if "city" in df.columns and pd.notna(row.get("city")) else None
        val_prov = str(row.get("province")).strip() if "province" in df.columns and pd.notna(row.get("province")) else None
        if val_city:
            if has_city:
                resp_kwargs["city"] = val_city
            elif has_loc_city:
                resp_kwargs["location_city"] = val_city
        if val_prov:
            if has_province:
                resp_kwargs["province"] = val_prov
            elif has_loc_province:
                resp_kwargs["location_province"] = val_prov

        if has_pp and pp_std:
            resp_kwargs["purchase_power"] = pp_std

        respondent = Respondent(**resp_kwargs)
        db.session.add(respondent)
        db.session.flush()

        # --- 其它列丢进 answers（可选，不阻断） ---
        exclude = {"age", "age_bucket", "gender", "city", "province"}
        if has_pp:
            exclude.add("purchase_power")
            
        answers = {}
        for c in df.columns:
            if c in exclude: 
                continue
            v = row.get(c)
            if pd.notna(v):
                answers[c] = str(v)
        if not has_pp and pp_std:
            answers["purchase_power"] = pp_std
        response = Response(survey_id=survey.id, respondent_id=respondent.id)
        db.session.add(response)
        db.session.flush()

        if resp_answer_fields and answers:
            answers_str = json.dumps(answers, ensure_ascii=False)
            setattr(response, resp_answer_fields[0], answers_str)  # 写到第一个存在的字段

        rows += 1

    db.session.commit()
    return rows