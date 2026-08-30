"""
最原始資料格式處理
"""

import numpy as np
import pandas as pd
from pathlib import Path
import re

# 取得當前工作目錄的上一層目錄作為專案根目錄
home_pth = Path.cwd().parents[0]
# 設定 L1 資料儲存路徑（第一層清理後的資料）
floder = home_pth.joinpath("using_data/L1")
Path.mkdir(floder, exist_ok=True, parents=True)

# --- 處理普大師資資料 ---
# 讀取普大師資原始 Excel 檔案，並指定標頭在第 4 列
university = pd.read_excel(
    home_pth.joinpath("raw/114.01.06-(108.10期-113.10期)-教1-給國際司.xlsx"), header=4
)
# 移除所有值均為 NaN 的欄位
university.dropna(axis="columns", how="all", inplace=True)
university.to_csv(floder.joinpath("普大師資.csv"), index=False)

# --- 處理科大師資資料 ---
collge = pd.read_csv(
    home_pth.joinpath("raw/114.01.06_(國際司)技專校院108至113上表1-1.csv"),
    # 指定代碼相關欄位為字串格式，避免讀取時因純數字而被誤判為數值型別
    dtype={
        "學校統計處代碼": "string",
        "主聘單位統計處系所代碼": "string",
        "合聘單位代碼(統計處)": "string",
    },
)
# 移除所有值均為 NaN 的欄位
collge.dropna(axis="columns", how="all", inplace=True)
collge.to_csv(floder.joinpath("科大師資.csv"), index=False)

# --- 處理公費錄取資料 ---
# 讀取公費錄取資料 Excel 檔案中的所有工作表
allsheets = pd.read_excel(
    home_pth.joinpath(
        "raw/※100-113公費各學門合格報名及錄取人數-1140106提供國教院.xlsx"
    ),
    sheet_name=None,  # sheet_name=None 會將所有工作表讀取成一個字典
)

admission = pd.DataFrame()

# 遍歷所有工作表進行處理與合併
for sheet_name, df in allsheets.items():
    # 使用正規表達式從工作表名稱中提取年度資訊 (e.g., "108公費" -> "108")
    pattern = r"(.*?)公費"
    match = re.search(pattern, sheet_name)

    if match:
        years = match.group(1)  # 取得匹配到的年度字串
        print(years)
    else:
        print("未找到匹配的内容")

    # 根據不同年度範圍，判斷標頭所在的列數
    if years == "106-107":
        print("年度106-107公費新南向各學門統計: 請手動處理")
        continue
    elif int(years) <= 106:
        header_number = 1
    else:
        header_number = 2

    # 根據判斷出的標頭列數，重新讀取該工作表
    df = pd.read_excel(
        home_pth.joinpath(
            "raw/※100-113公費各學門合格報名及錄取人數-1140106提供國教院.xlsx"
        ),
        sheet_name=sheet_name,
        header=header_number,  # 使用正確的標頭列
    )
    # 新增一欄 '年度'，並填入從工作表名稱提取的年度
    df["年度"] = int(years)
    print(df.columns)
    admission = pd.concat([admission, df], axis=0, ignore_index=True)

# --- 公費錄取資料後續清理 ---
# 使用 "報名總人數" 填充 "報名人數" 欄位的缺失值
admission["報名人數"] = admission["報名人數"].fillna(admission["報名總人數"])
# 移除所有值均為 NaN 的欄位
admission.dropna(axis="columns", how="all", inplace=True)
# 移除不需要的欄位
admission.drop(["報名總人數"], axis=1, inplace=True)
admission = admission.loc[admission["學門編碼"] != "合計", :]

# 將最終清理完成的公費錄取資料存為 CSV 檔
admission.to_csv(floder.joinpath("公費錄取.csv"), index=False)
