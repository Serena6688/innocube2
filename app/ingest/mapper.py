import re, pandas as pd

AGE_COLS = ['年龄','年龄段','q1.请问您的年龄是？','age']
PP_COLS  = ['购买力等级','购买力','消费能力','消费水平','purchase_power','purchasing power']

def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns: return c
    return None

def age_to_bucket(v):
    if pd.isna(v): return None, None
    s = str(v).strip()
    m = re.search(r'(\d{2})\D{0,2}(\d{2})', s)
    if m: return None, f"{m.group(1)}-{m.group(2)}"
    if re.search(r'60.*(上|以上|\+)', s): return None, "60+"
    if re.fullmatch(r'\d{1,2}', s):
        a = int(s)
        for hi,label in [(24,'18-24'),(29,'25-29'),(34,'30-34'),(39,'35-39'),
                         (44,'40-44'),(49,'45-49'),(54,'50-54'),(59,'55-59')]:
            if a<=hi: return a,label
        return a,"60+"
    return None, None

def norm_pp(v):
    if v is None or (isinstance(v,float) and pd.isna(v)): return None
    s = str(v).strip().lower()
    mapping={'高':'High','较高':'High','很高':'High','偏高':'High',
             '中':'Medium','中等':'Medium','一般':'Medium','适中':'Medium',
             '低':'Low','较低':'Low','很低':'Low','偏低':'Low',
             'high':'High','medium':'Medium','low':'Low'}
    if s in mapping: return mapping[s]
    if re.fullmatch(r'\d+(\.\d+)?', s):
        x=float(s)
        if 1<=x<=5:   return 'Low' if x<=2 else ('Medium' if x<4 else 'High')
        if 0<=x<=100: return 'Low' if x<34 else ('Medium' if x<67 else 'High')
    return str(v).strip()