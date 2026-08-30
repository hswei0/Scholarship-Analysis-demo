import pandas as pd
import glob
from pathlib import Path

# 取得當前工作目錄的上一層目錄作為專案根目錄
home_pth = Path.cwd().parents[1]
# 設定 L2 資料儲存路徑
floder = home_pth.joinpath("using_data/L2")


def format_code(code, code_type):
    """
    標準化代碼格式，確保代碼為固定長度的字串並在前方補零。

    原因：
    不同來源的代碼可能因儲存格式（如數值、文字）而失去前導零，
    例如 '05' 可能被讀取為 5.0。此函式旨在統一格式，以便後續能正確比對與合併。

    Args:
        code: 原始代碼 (可能為數值、字串或 NaN)。
        code_type (str): 代碼類型，用於判斷應補足的長度。

    Returns:
        str: 格式化後的代碼字串；若輸入為 NaN，則返回空字串。
    """
    if pd.isna(code):
        return ""
    # 將代碼轉為字串，並移除可能因 Excel/Pandas 自動轉換產生的 '.0'
    code_str = str(code).replace(".0", "")

    # 根據代碼類型進行格式化
    if code_type == "領域代碼":
        return code_str.zfill(2)  # 2碼數字
    elif code_type == "學門代碼":
        return code_str.zfill(3)  # 3碼數字
    elif code_type == "學類代碼":
        return code_str.zfill(4)  # 4碼數字
    elif code_type == "細學類代碼":
        return code_str.zfill(5)  # 5碼數字
    return code_str


def process_csv_files(file_path):
    """
    讀取並初步處理單個學歷分類的 CSV 檔案。

    設計考量：
    - 原始 CSV 檔案可能由人工編輯，格式不一，因此採用較寬鬆的讀取設定以提高成功率。
      - `on_bad_lines='skip'`: 跳過格式錯誤的行。
      - `engine='python'`: 使用更具彈性的 Python 引擎處理複雜或不標準的 CSV。
    - 確保所有後續處理所需的欄位都存在，若缺少則提出警告。
    - 標準化代碼格式，並確保細學類相關欄位存在，以利後續合併。
    """
    try:
        # 使用更寬鬆的CSV讀取設定
        df_temp = pd.read_csv(
            file_path,
            encoding="utf-8",
            # 以下參數是為了處理可能不規則的 CSV 格式，增強讀取穩定性
            on_bad_lines="skip",
            quoting=1,
            escapechar="\\",
            engine="python",
        )

        # 確保所有必要的欄位都存在
        required_columns = ["領域代碼", "學門代碼", "學類代碼"]
        if not all(col in df_temp.columns for col in required_columns):
            print(f"警告：檔案 {file_path} 缺少必要的欄位")
            return None

        code_columns = {
            "領域代碼": "領域代碼",
            "學門代碼": "學門代碼",
            "學類代碼": "學類代碼",
        }

        # 處理代碼格式化
        for col, code_type in code_columns.items():
            if col in df_temp.columns:
                df_temp[col] = df_temp[col].apply(lambda x: format_code(x, code_type))

        # 添加細學類相關欄位（如果不存在）
        # 目的：統一不同來源檔案的 Schema，若無細學類資料，則以學類資料作為預設值
        if "細學類代碼" not in df_temp.columns:
            df_temp["細學類代碼"] = df_temp["學類代碼"]
        if "細學類名稱" not in df_temp.columns:
            df_temp["細學類名稱"] = df_temp["學類名稱"]

        return df_temp

    except Exception as e:
        print(f"處理檔案 {file_path} 時發生錯誤：{str(e)}")
        return None


def process_and_merge_files():
    """
    整合公費生主資料與由 AI (Grok) 及人工校正後的國內、外學歷分類資料。
    流程：
    1. 讀取公費生主資料檔。
    2. 讀取並合併所有國內最高學歷的分類結果 CSV。
    3. 讀取並合併所有國外學歷的分類結果 CSV。
    4. 重新命名欄位以區分國內外學歷，避免合併時衝突。
    5. 將分類結果合併回主資料檔。
    6. 儲存最終結果。
    """
    # 讀取原始Excel檔案
    target_file = floder.joinpath(
        "0113_103~112錄取年_獲公費獎學金者回國相關數據資料V3.xlsx"
    )
    df_target = pd.read_excel(target_file, header=1)

    # 讀取並處理最高學歷比對資料夾中的所有CSV檔案
    highest_education_path = str(home_pth) + "/using_data/系所比對/最高學歷/*.csv"
    df1_list = []

    for file_path in glob.glob(highest_education_path):
        df_temp = process_csv_files(file_path)
        if df_temp is not None:
            df1_list.append(df_temp)

    if not df1_list:
        raise Exception("沒有成功讀取任何最高學歷CSV檔案")

    # 合併所有最高學歷的資料
    df1 = pd.concat(df1_list, ignore_index=True)

    # 讀取並處理國外學校資料夾中的所有CSV檔案
    foreign_education_path = str(home_pth) + "/using_data/系所比對/國外學校0529/*.csv"
    df2_list = []

    for file_path in glob.glob(foreign_education_path):
        df_temp = process_csv_files(file_path)
        if df_temp is not None:
            # 檢查原始系所欄位名稱
            if "系所" in df_temp.columns:
                df_temp = df_temp.rename(columns={"系所": "原始系所"})
            elif "原始系所" not in df_temp.columns:
                print(f"警告：檔案 {file_path} 缺少原始系所欄位")
                continue

            # 檢查原始系所名稱是否為空白
            # 如果原始系所名稱為空，代表該筆資料的學歷分類無效，因此將相關欄位清空以避免錯誤合併。
            mask = df_temp["原始系所"].isna() | (df_temp["原始系所"] == "")
            columns_to_reset = [col for col in df_temp.columns if col != "序號"]
            df_temp.loc[mask, columns_to_reset] = ""
            df2_list.append(df_temp)

    if not df2_list:
        raise Exception("沒有成功讀取任何國外學校CSV檔案")

    # 合併所有國外學校的資料
    df2 = pd.concat(df2_list, ignore_index=True)

    # 為欄位加上後綴，以區分「國內最高學歷」與「國外學歷」的分類結果
    df1_columns = {
        "序號": "序",
        "領域代碼": "領域代碼_最高學系",
        "領域名稱": "領域名稱_最高學系",
        "學門代碼": "學門代碼_最高學系",
        "學門名稱": "學門名稱_最高學系",
        "學類代碼": "學類代碼_最高學系",
        "學類名稱": "學類名稱_最高學系",
        "細學類代碼": "細學類代碼_最高學系",
        "細學類名稱": "細學類名稱_最高學系",
    }

    df2_columns = {
        "序號": "序",
        "領域代碼": "領域代碼_國外學歷",
        "領域名稱": "領域名稱_國外學歷",
        "學門代碼": "學門代碼_國外學歷",
        "學門名稱": "學門名稱_國外學歷",
        "學類代碼": "學類代碼_國外學歷",
        "學類名稱": "學類名稱_國外學歷",
    }

    # 重命名欄位
    df1 = df1.rename(columns=df1_columns)
    df2 = df2.rename(columns=df2_columns)

    # 合併處理後的資料
    keep1 = [
        "序",
        "領域代碼_最高學系",
        "領域名稱_最高學系",
        "學門代碼_最高學系",
        "學門名稱_最高學系",
        "學類代碼_最高學系",
        "學類名稱_最高學系",
        "細學類代碼_最高學系",
        "細學類名稱_最高學系",
    ]
    keep2 = [
        "序",
        "領域代碼_國外學歷",
        "領域名稱_國外學歷",
        "學門代碼_國外學歷",
        "學門名稱_國外學歷",
        "學類代碼_國外學歷",
        "學類名稱_國外學歷",
    ]
    df_merged = pd.merge(df_target, df1[keep1], on="序", how="left")
    df_merged = pd.merge(df_merged, df2[keep2], on="序", how="left")

    # 將合併後的資料輸出為新的CSV檔案
    output_file = floder.joinpath("合併後的分類結果0529.csv")
    # 使用 'utf-8-sig' 編碼以確保在 Windows 上的 Excel 能正確顯示中文字元 (帶有BOM)
    df_merged.to_csv(output_file, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    process_and_merge_files()
