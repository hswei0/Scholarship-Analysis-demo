import pandas as pd
from pathlib import Path
import re

# home_pth = Path.cwd().parents[0]

# file_path = home_pth.joinpath("using_data/L2/faculty.csv")
# df_headers = pd.read_csv(file_path, nrows=0)
# # 找出所有包含「代碼」的欄位名稱
# code_columns = [col for col in df_headers.columns if "代碼" in col]
# # 建立 dtype 字典，將特定欄位設定為字串格式
# dtype_dict = {col: "str" for col in code_columns}
# faculty = pd.read_csv(file_path, dtype=dtype_dict)
# faculty.drop(columns=["是否新進"], inplace=True)


def analyze_employee_changes(df, domain_column="領域名稱"):
    """
    分析各學年度各領域的新進和離開人員，
    此函式為典型的面板資料（Panel Data）分析，用於追蹤個體在不同時間點的狀態變化。

    核心邏輯：
    - 新進定義：在某個分析單位（領域-學校類別組合）中，於當前學年度首次出現的 pseudoID。
    - 離開定義：在某個分析單位中，於當前學年度出現後，在後續所有學年度皆未再出現的 pseudoID。

    注意事項：
    - pseudoID 為基於個人特徵生成的偽識別碼，不保證與真實個人完全對應。
    - 「離開」狀態無法判斷資料集中的最後一個學年度，因無後續資料可供比對。
    - 分析單位為「領域」與「學校類別」的組合，人員在不同單位間的流動會被視為離開舊單位、進入新單位。

    Parameters:
    df: pandas DataFrame，需包含必要欄位
    domain_column: str, 領域欄位的名稱，預設為 '領域名稱'

    Returns:
    DataFrame: 包含新增 '是否新進' 和 '是否離開' 欄位的原始資料
    dict: 包含每學校類別/學年度/領域新進員工pseudoID列表的巢狀字典
    dict: 包含每學校類別/學年度/領域離開員工pseudoID列表的巢狀字典
    DataFrame: 包含每位員工首次出現學年度和領域的DataFrame
    DataFrame: 包含年度異動統計的DataFrame
    """
    # 確認必要欄位存在
    required_columns = {
        "pseudoID",
        "學年度",
        "學校類別",
        domain_column,
    }
    if not required_columns.issubset(df.columns):
        missing_cols = required_columns - set(df.columns)
        raise ValueError(f"缺少必要欄位: {missing_cols}")

    # 製作原始資料的複本並篩選編制內專任教師
    result_df = df.copy()
    result_df["學年度"] = pd.to_numeric(result_df["學年度"], errors="coerce")

    # 篩選條件
    # condition = (result_df["編制內外"] == "編制內") & (result_df["專兼任"] == "專任")
    # result_df = result_df[condition].copy()

    # 取得學年度範圍、領域列表和學校類別
    years = sorted(result_df["學年度"].dropna().unique())
    domains = sorted(result_df[domain_column].dropna().unique())
    school_types = sorted(result_df["學校類別"].dropna().unique())

    # 建立儲存結果的巢狀字典
    new_employees = {
        school_type: {year: {domain: [] for domain in domains} for year in years}
        for school_type in school_types
    }
    leaving_employees = {
        school_type: {year: {domain: [] for domain in domains} for year in years}
        for school_type in school_types
    }

    # 初始化年度異動統計DataFrame
    yearly_stats = []

    # 找出每個員工在每個領域和學校類別第一次出現的學年度
    first_appearance = (
        result_df.groupby(["pseudoID", domain_column, "學校類別"])["學年度"]
        .min()
        .reset_index()
    )
    first_appearance.columns = ["pseudoID", domain_column, "學校類別", "首次出現學年度"]

    # 初始化 '是否新進' 和 '是否離開' 欄位
    result_df["是否新進"] = False
    result_df["是否離開"] = False

    # 對每個學校類別、學年度和領域進行分析
    for school_type in school_types:
        for year in years:
            for domain in domains:
                # 建立遮罩條件
                domain_mask = result_df[domain_column] == domain
                school_mask = result_df["學校類別"] == school_type
                combined_mask = domain_mask & school_mask

                # 取得該年度該組合的員工
                current_year_ids = set(
                    result_df[combined_mask & (result_df["學年度"] == year)][
                        "pseudoID"
                    ].unique()
                )

                # 取得所有過去年度在該組合出現過的員工
                past_years_ids = set(
                    result_df[combined_mask & (result_df["學年度"] < year)][
                        "pseudoID"
                    ].unique()
                )

                # 新進員工：當年度出現且過去從未出現過的
                new_ids = [id for id in current_year_ids if id not in past_years_ids]
                new_employees[school_type][year][domain] = new_ids

                # 標註新進員工
                result_df.loc[
                    (result_df["學年度"] == year)
                    & combined_mask
                    & (result_df["pseudoID"].isin(new_ids)),
                    "是否新進",
                ] = True

                # 處理離開員工：檢查之後是否都沒出現
                if year < years[-1]:  # 不處理最後一年的離開統計
                    current_ids = set(
                        result_df[combined_mask & (result_df["學年度"] == year)][
                            "pseudoID"
                        ].unique()
                    )

                    # 檢查這些員工在之後的年度是否都沒出現
                    future_years_mask = (result_df["學年度"] > year) & combined_mask
                    future_ids = set(result_df[future_years_mask]["pseudoID"].unique())

                    leaving_ids = [id for id in current_ids if id not in future_ids]
                    leaving_employees[school_type][year][domain] = leaving_ids

                    # 標註離開員工
                    result_df.loc[
                        (result_df["學年度"] == year)
                        & combined_mask
                        & (result_df["pseudoID"].isin(leaving_ids)),
                        "是否離開",
                    ] = True

                # 逐年、逐領域、逐學校類別計算統計數據
                new_count = len(new_employees[school_type][year][domain])
                leaving_count = (
                    len(leaving_employees[school_type][year][domain])
                    if year < years[-1]
                    else 0
                )

                yearly_stats.append(
                    {
                        "學年度": year,
                        "學校類別": school_type,
                        "領域": domain,
                        "新進人數": new_count,
                        "離開人數": leaving_count,
                        "淨異動人數": new_count - leaving_count,
                    }
                )

    # 建立年度統計DataFrame
    stats_df = pd.DataFrame(yearly_stats)

    return result_df, new_employees, leaving_employees, first_appearance, stats_df


# condition = (
#     (faculty["編制內外"] == "編制內")
#     & (faculty["專兼任"] == "專任")
#     & (faculty["學校類別"] != "宗教研修學院")
# )
# using_df = faculty[condition].copy()

# result_df, new_emps, leaving_emps, first_app, yearly_stats = analyze_employee_changes(
#     faculty
# )


# condition2 = (
#     (result_df["編制內外"] == "編制內")
#     & (result_df["專兼任"] == "專任")
#     & (result_df["學校類別"] != "宗教研修學院")
# )

# df1 = result_df[
#     (result_df["學年度"].isin(range(109, 113))) & (result_df["學期"] == 1) & condition2
# ]
# df1["退休離開"] = (df1["年齡"] >= 64) & df1["是否離開"]

# dt = df1.pivot_table(
#     index=["領域代碼", "領域名稱"],
#     columns="學年度",
#     values=["pseudoID", "是否新進", "是否離開"],
#     aggfunc={"pseudoID": "count", "是否新進": "sum", "是否離開": "sum"},
# )

# pd.options.display.precision = 2

# dt2 = df1[df1["是否離開"]].pivot_table(
#     index=["學校類別", "領域代碼", "領域名稱"],
#     columns="學年度",
#     values=["是否離開", "退休離開"],
#     aggfunc={"是否離開": "sum", "退休離開": "mean"},
# )

# # 新進來源分析
# local_sch = faculty["學校名稱"].unique()
# # 少數台灣學校判斷錯誤
# df1["local_phd"] = df1["最高學歷學校"].isin(local_sch)

# df1[df1["是否新進"]].pivot_table(
#     index=["學校類別", "領域代碼", "領域名稱"],
#     columns="學年度",
#     values=["是否新進", "local_phd"],
#     aggfunc={"是否新進": "sum", "local_phd": "mean"},
# )
