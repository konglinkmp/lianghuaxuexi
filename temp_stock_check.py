import pandas as pd
import akshare as ak
import os
import sys

# 设置路径
csv_path = "/Users/chenbowen/workspace/quant/data/reports/trading_plan.csv"
zhgk_code = "600862"

def get_analysis():
    print("--- 交易计划内容 ---")
    if os.path.exists(csv_path):
        try:
            plan_df = pd.read_csv(csv_path, dtype={'代码': str})
            print(plan_df[['代码', '名称', '操作建议', '建议买入价']].to_string())
            plan_codes = plan_df['代码'].tolist()
        except Exception as e:
            print(f"读取CSV失败: {e}")
            plan_codes = []
    else:
        print("未找到 trading_plan.csv")
        plan_codes = []

    all_codes = list(set(plan_codes + [zhgk_code]))
    
    print("\n--- 集合竞价/实时行情 (9:26) ---")
    try:
        # 获取最新的快照数据
        snapshot = ak.stock_zh_a_spot_em()
        if snapshot is not None and not snapshot.empty:
            target_df = snapshot[snapshot['代码'].isin(all_codes)]
            # 整理输出列
            output_cols = ['代码', '名称', '最新价', '涨跌幅', '开盘价', '最高价', '最低价', '成交量', '成交额']
            # 注意：akshare 返回的列名可能略有不同，匹配一下
            existing_cols = [c for c in output_cols if c in target_df.columns]
            print(target_df[existing_cols].to_string(index=False))
        else:
            print("未能获取实时行情快照")
    except Exception as e:
        print(f"获取行情失败: {e}")

if __name__ == "__main__":
    get_analysis()
