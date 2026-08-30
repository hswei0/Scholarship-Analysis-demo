"""
從「學2-1...csv」計算博士班畢業人數。
同時處理「一般大學」與「技專」的資料。

輸出檔：
- report/YYYYMMDD/博士班畢業人數_一般大學_總覽.xlsx
- report/YYYYMMDD/博士班畢業人數_技專_總覽.xlsx

使用方法（在專案根目錄下執行）：
    /Users/hsuwei/.julia/conda/3/aarch64/bin/python3 src/02_phd_graduates_analysis.py
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date

# ── 路徑設定 ──────────────────────────────────────────────
home_pth = Path(__file__).resolve().parents[1]          # 專案根目錄
MOE_CODE = home_pth / "using_data/L1/學門代碼表.csv"
FACULTY_CSV = home_pth / "using_data/L2/faculty.csv"   # 用來查研究型大學清單

today_str = date.today().strftime("%Y%m%d")
OUT_DIR = home_pth / f"report/{today_str}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 定義要處理的學校分類與對應輸入檔
TASK_CONFIG = {
    "一般大學": home_pth / "學2-1.畢業生數及其取得輔系、雙主修資格人數-以「系(所)」統計 105-113 一般大學.csv",
    "技專": home_pth / "學2-1.畢業生數及其取得輔系、雙主修資格人數-以「系(所)」統計 105-113 技專.csv",
}

# ── 讀取代碼表 ──────────────────────────────────────────────
def read_with_code_columns(path):
    headers = pd.read_csv(path, nrows=0)
    code_cols = [c for c in headers.columns if "代碼" in c]
    dtype = {c: str for c in code_cols}
    return pd.read_csv(path, dtype=dtype)

moe_code = read_with_code_columns(MOE_CODE)

fac_headers = pd.read_csv(FACULTY_CSV, nrows=0)
fac_code_cols = [c for c in fac_headers.columns if "代碼" in c]
fac_dtype = {c: str for c in fac_code_cols}
faculty = pd.read_csv(FACULTY_CSV, dtype=fac_dtype)

# ── 排序用清單 ───────────────────────────────────────────────
MAIN_FIELDS_ORDER = [
    "製造及加工學門", "建築及營建工程學門", "工程及工程業學門",
    "資訊通訊科技學門", "人文學門", "醫藥衛生學門", "藝術學門",
    "林業學門", "獸醫學門", "物理、化學及地球科學學門", "教育學門",
    "語文學門", "運輸服務學門", "社會福利學門", "農業學門",
    "生命科學學門", "數學及統計學門", "商業及管理學門",
    "新聞學及圖書資訊學門", "社會及行為科學學門", "環境學門",
    "法律學門", "其他學門", "餐旅及民生服務學門", "漁業學門",
    "衛生及職業衛生服務學門", "安全服務學門",
]

def sort_by_field(df, field_col="學門名稱", year_col="學年度"):
    order = {f: i for i, f in enumerate(MAIN_FIELDS_ORDER)}
    df = df.copy()
    df["__sort__"] = df[field_col].map(order).fillna(9999)
    df = df.sort_values([year_col, "__sort__"]).drop(columns=["__sort__"])
    return df

IDX = ["學年度", "領域名稱", "學門名稱", "細學類名稱", "細學類代碼"]
SCHOOL_TYPES = ["公立", "研究型", "私立"]


def process_school_type(school_class_name, raw_csv_path):
    print(f"\n======== 開始處理：{school_class_name} ========")
    out_xlsx_path = OUT_DIR / f"博士班畢業人數_{school_class_name}_總覽.xlsx"

    print("1. 讀取原始 CSV …")
    raw = pd.read_csv(
        raw_csv_path,
        dtype={"學校統計處代碼": str, "系所代碼": str},
    )
    phd = raw[raw["學制班別"] == "博士班"].copy()
    print(f"  博士班記錄數：{len(phd)}")

    print("2. 合併學門代碼表 …")
    phd["細學類代碼"] = phd["系所代碼"].str.slice(0, 5)
    phd = phd.merge(moe_code, how="left", on="細學類代碼")

    fill_map = {
        "領域代碼": "99", "領域名稱": "其他領域",
        "學門代碼": "999", "學門名稱": "其他學門",
        "學類代碼": "9999", "學類名稱": "其他學類",
        "細學類代碼": "99999", "細學類名稱": "其他細學類",
    }
    for col, val in fill_map.items():
        phd[col] = phd[col].fillna(val)

    print("3. 標注研究型大學 …")
    # 對應 faculty.csv 中的學校類別欄位
    # 「一般大學」對應 '一般大學', 「技專」對應 '技專校院'
    fac_school_class = '一般大學' if school_class_name == '一般大學' else '技專校院'
    research_uni_codes = (
        faculty
        .query(f"學校類別 == '{fac_school_class}' and 研究型大學 == True")
        .drop_duplicates(subset=["學校統計處代碼"])
        ["學校統計處代碼"]
        .tolist()
    )

    phd["研究型大學"] = phd["學校統計處代碼"].isin(research_uni_codes)
    phd["設立別_展示"] = phd.apply(
        lambda x: "研究型" if x["研究型大學"] else x["設立別"], axis=1
    )

    print("4. 計算全體學校博士畢業人數 …")
    tb_all = (
        phd
        .groupby(IDX, as_index=False)["畢業生數小計"]
        .sum()
        .rename(columns={"畢業生數小計": "博士畢業人數"})
    )
    tb_all = sort_by_field(tb_all)

    print("5. 計算分設立別博士畢業人數 …")
    tb_split_raw = phd.pivot_table(
        values="畢業生數小計",
        index=IDX,
        columns="設立別_展示",
        aggfunc="sum",
        fill_value=0,
    )
    
    for st in SCHOOL_TYPES:
        if st not in tb_split_raw.columns:
            tb_split_raw[st] = 0
    tb_split_raw = tb_split_raw[SCHOOL_TYPES]
    tb_split_raw.columns = pd.MultiIndex.from_product(
        [["博士畢業人數"], SCHOOL_TYPES]
    )
    tb_split_raw = tb_split_raw.reset_index()

    tb_split = tb_split_raw.copy()
    tb_split.columns = [
        "_".join(c).strip("_") if isinstance(c, tuple) else c
        for c in tb_split.columns
    ]
    tb_split = sort_by_field(tb_split)

    print(f"6. 輸出至 {out_xlsx_path} …")
    with pd.ExcelWriter(out_xlsx_path, engine="openpyxl") as writer:
        tb_all.to_excel(writer, sheet_name="全體學校", index=False)
        tb_split.to_excel(writer, sheet_name="分設立別", index=False)

    print(f"  {school_class_name} 完成！全體學校：{len(tb_all)} 列, 分設立別：{len(tb_split)} 列")


if __name__ == "__main__":
    for school_class_name, raw_csv_path in TASK_CONFIG.items():
        process_school_type(school_class_name, raw_csv_path)
