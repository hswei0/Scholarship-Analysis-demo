"""
分析用資料清理工作
"""

from pathlib import Path
import hashlib
import pandas as pd

home_pth = Path.cwd().parents[0]
floder = home_pth.joinpath("using_data/L2")
floder.mkdir(parents=True, exist_ok=True)


def read_table_with_code_columns(file_path):
    """讀取表格，將所有以「代碼」結尾的欄位設定為字串格式。

    此函數首先判斷檔案類型（目前支援 .xlsx 和 .csv），
    然後將所有名稱以「代碼」結尾的欄位設定為字串dtype，以確保代碼的正確讀取與處理。

    Args:file_path (str): 檔案路徑
    Returns:
    pandas.DataFrame: 處理後的資料框
    """
    # 判斷檔案類型
    file_extension = file_path.suffix

    if file_extension == ".xlsx":
        # 首先讀取檔案的標題列
        df_headers = pd.read_excel(file_path, nrows=0)
    elif file_extension == ".csv":
        df_headers = pd.read_csv(file_path, nrows=0)
    else:
        raise ValueError("Unsupported file type: {}".format(file_extension))

    # 找出所有以「代碼」結尾的欄位名稱
    code_columns = [col for col in df_headers.columns if col.endswith("代碼")]

    # 建立 dtype 字典，將特定欄位設定為字串格式
    dtype_dict = {col: str for col in code_columns}

    # 讀取檔案，並套用 dtype 設定
    if file_extension == ".xlsx":
        df = pd.read_excel(file_path, dtype=dtype_dict)
    elif file_extension == ".csv":
        df = pd.read_csv(file_path, dtype=dtype_dict)

    return df


def generate_md5_id(row):
    """為給定的資料列產生一個MD5雜湊值作為ID。

    此函式接收一個包含個人資料的字典 (row)，並將性別、出生年月日、
    最高學歷學校和最高學歷學系等欄位串聯成一個字串，然後計算該字串的
    MD5雜湊值。此雜湊值將作為該資料列的唯一識別ID。

    Args:
        row (dict): 包含個人資料的字典，預期包含以下鍵：
            - "性別" (str): 性別
            - "出生年月日" (str/datetime): 出生年月日
            - "最高學歷學校" (str): 最高學歷學校名稱
            - "最高學歷學系" (str): 最高學歷學系名稱

    Returns:
        str: 資料列的MD5雜湊值，以十六進位字串表示。

    Raises:
        TypeError: 如果輸入的row不是字典。
        KeyError: 如果row缺少任何預期的鍵 (性別, 出生年月日, 最高學歷學校, 最高學歷學系)。
    """
    s = (
        str(row["性別"])
        + str(row["出生年月日"])
        + str(row["最高學歷學校"])
        + str(row["最高學歷學系"])
    )
    return hashlib.md5(s.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    print("這部分只有在直接運行此模組時才會被執行")

    # 普大資料

    university = pd.read_csv(
        home_pth.joinpath("using_data/L1/普大師資.csv"),
        dtype={"學校統計處代碼": "string", "主聘單位統計處系所代碼": "string"},
        # nrows=100,
    )

    # 科大資料
    collge = pd.read_csv(
        home_pth.joinpath("using_data/L1/科大師資.csv"),
        dtype={
            "學校統計處代碼": "string",
            "主聘單位統計處系所代碼": "string",
            "合聘單位代碼(統計處)": "string",
        },
    )

    all_df = pd.concat(
        [university, collge], axis=0, ignore_index=True
    )  # 合併大專院校資料

    # 分析用處理
    all_df["出生年"] = all_df["出生年月日"].str.slice(0, 4).astype("int")
    all_df["年齡"] = 1911 + all_df["學年度"] - all_df["出生年"]
    all_df["細學類代碼"] = all_df["主聘單位統計處系所代碼"].str.slice(0, 5)
    all_df.replace({"學期": {"上": 1, "下": 2}}, inplace=True)
    all_df["female"] = all_df["性別"] == "女"

    # 人員身分證
    # 使用 MD5 雜湊函數
    all_df["pseudoID"] = all_df.apply(generate_md5_id, axis=1)

    # 併入代碼表
    moe_code = read_table_with_code_columns(
        home_pth.joinpath("using_data/L1/學門代碼表.csv")
    )

    all_df = all_df.merge(moe_code, how="left", on="細學類代碼")

    # 標註研究型大學
    schools = read_table_with_code_columns(
        home_pth.joinpath("using_data/L1/113學年度大專校院系所彙整表(以學院分類).csv")
    ).drop_duplicates(subset=["學校代碼"])

    # 處理陽明交大
    all_df.loc[all_df["學校統計處代碼"] == "0016", ["學校統計處代碼", "學校名稱"]] = [
        "0007",
        "國立陽明交通大學",
    ]
    all_df.loc[all_df["學校統計處代碼"] == "0007", ["學校統計處代碼", "學校名稱"]] = [
        "0007",
        "國立陽明交通大學",
    ]

    all_df = all_df.merge(
        schools[["學校代碼", "研究型大學"]],
        how="left",
        left_on="學校統計處代碼",
        right_on="學校代碼",
        indicator=False,
    )  # 合併結果會有倒閉的學校、陽明大學
    all_df["研究型大學"].fillna(False, inplace=True)
    all_df.drop(columns=["學校代碼"], inplace=True)

    all_df.to_csv(floder.joinpath("faculty.csv"), index=False)

    # FIXME:後續可再進行分析
    # 標注新進人員

    # def is_new_employee(df, domain_column="領域名稱"):
    #     """
    #     分析各學年度各領域「編制內」、「專任」的新進員工，並在原始資料中標註新進員工，
    #     需要注意pseudoID為推定的個人，不一定符合現實。
    #     並且這是以整個「領域」範圍來判定。

    #     Parameters:
    #     df: pandas DataFrame，需包含 'pseudoID'、'學年度' 和領域欄位
    #     domain_column: str, 領域欄位的名稱，預設為 '領域名稱'

    #     Returns:
    #     DataFrame: 包含新增 '是否新進' 欄位的原始資料
    #     dict: 包含每學年度每領域新進員工pseudoID列表的巢狀字典
    #     DataFrame: 包含每位員工首次出現學年度和領域的DataFrame
    #     """
    #     # 確認必要欄位存在
    #     required_columns = {
    #         "pseudoID",
    #         "學年度",
    #         "編制內外",
    #         "專兼任",
    #         "學校類別",
    #         domain_column,
    #     }
    #     if not required_columns.issubset(df.columns):
    #         missing_cols = required_columns - set(df.columns)
    #         raise ValueError(f"缺少必要欄位: {missing_cols}")

    #     result_df = df.copy()
    #     result_df["學年度"] = pd.to_numeric(result_df["學年度"], errors="coerce")

    #     # 取得學年度範圍和領域列表
    #     years = sorted(result_df["學年度"].dropna().unique())
    #     domains = sorted(result_df[domain_column].dropna().unique())
    #     school_types = sorted(result_df["學校類別"].dropna().unique())

    #     # 建立儲存結果的巢狀字典
    #     new_employees = {
    #         school_type: {year: {domain: [] for domain in domains} for year in years}
    #         for school_type in school_types
    #     }

    #     # 找出每個員工在每個領域第一次出現的學年度
    #     first_appearance = (
    #         df.query("`編制內外` == '編制內' & `專兼任` == '專任'")
    #         .groupby(["pseudoID", domain_column, "學校類別"])["學年度"]
    #         .min()
    #         .reset_index()
    #     )
    #     first_appearance.columns = ["pseudoID", domain_column, "學校類別", "首次出現學年度"]

    #     # 初始化 '是否新進' 欄位
    #     result_df["是否新進"] = False

    #     # 對每個學校類別、學年度和領域進行分析
    #     for school_type in school_types:
    #         for year in years:
    #             for domain in domains:
    #                 # 建立遮罩條件
    #                 domain_mask = result_df[domain_column] == domain
    #                 school_mask = result_df["學校類別"] == school_type
    #                 combined_mask = domain_mask & school_mask

    #                 if year == years[0]:  # 第一年該領域和學校類別全部都視為新進
    #                     current_employees = result_df[
    #                         (combined_mask) & (result_df["學年度"] == year)
    #                     ]["pseudoID"].unique()
    #                     new_employees[school_type][year][
    #                         domain
    #                     ] = current_employees.tolist()
    #                     result_df.loc[
    #                         (result_df["學年度"] == year) & combined_mask, "是否新進"
    #                     ] = True
    #                 else:
    #                     # 該學年度在該領域和學校類別有出現，且之前學年度在該組合都沒出現的員工
    #                     previous_ids = result_df[
    #                         (combined_mask) & (result_df["學年度"] < year)
    #                     ]["pseudoID"].unique()
    #                     current_ids = result_df[
    #                         (combined_mask) & (result_df["學年度"] == year)
    #                     ]["pseudoID"].unique()
    #                     new_ids = [id for id in current_ids if id not in previous_ids]
    #                     new_employees[school_type][year][domain] = new_ids

    #                     # 標註新進員工
    #                     result_df.loc[
    #                         (result_df["學年度"] == year)
    #                         & combined_mask
    #                         & (result_df["pseudoID"].isin(new_ids)),
    #                         "是否新進",
    #                     ] = True

    #     return result_df, new_employees, first_appearance

    # 需注意分析單位為領域
    # all_df, new_emps, first_app = is_new_employee(all_df, "領域名稱")
    # all_df, new_emps, leaving_emps, first_app, yearly_stats = analyze_employee_changes(
    #     all_df
    # )

    # profile = ProfileReport(university, title="Profiling Report")
    # profile.to_file(home_pth.joinpath("普大描述.html"))

    # # 公費錄取
    # allsheets = pd.read_excel(
    #     home_pth.joinpath(
    #         "raw/※100-113公費各學門合格報名及錄取人數-1140106提供國教院.xlsx"
    #     ),
    #     sheet_name=None,
    # )  # sheet_name=None 會產生字典檔

    # admission = pd.DataFrame()

    # for sheet_name, df in allsheets.items():
    #     pattern = r"(.*?)公費"
    #     match = re.search(pattern, sheet_name)

    #     if match:
    #         years = match.group(1)
    #         print(years)
    #     else:
    #         print("未找到匹配的内容")

    #     if years == "106-107":
    #         print("年度106-107公費新南向各學門統計: 請手動處理")
    #         continue
    #     elif int(years) <= 106:
    #         header_number = 1
    #     else:
    #         header_number = 2

    #     df = pd.read_excel(
    #         home_pth.joinpath(
    #             "raw/※100-113公費各學門合格報名及錄取人數-1140106提供國教院.xlsx"
    #         ),
    #         sheet_name=sheet_name,
    #         header=header_number,
    #     )
    #     df["年度"] = int(years)
    #     print(df.columns)
    #     admission = pd.concat([admission, df], axis=0, ignore_index=True)

    # admission["報名人數"] = admission["報名人數"].fillna(admission["報名總人數"])
    # admission.dropna(axis="columns", how="all", inplace=True)
    # admission.drop(["報名總人數"], axis=1, inplace=True)
    # admission = admission.loc[admission["學門編碼"] != "合計", :]
    # admission.to_csv(floder.joinpath("公費錄取.csv"), index=False)
