import json
import os
import pandas as pd
from quant.strategy.stock_classifier import stock_classifier, LAYER_AGGRESSIVE, LAYER_CONSERVATIVE
from quant.core.data_fetcher import get_stock_daily_history, get_stock_industry
from config.config import POSITION_FILE

def analyze_held_stocks():
    if not os.path.exists(POSITION_FILE):
        print("No positions found.")
        return

    with open(POSITION_FILE, "r", encoding="utf-8") as f:
        positions = json.load(f)

    print("\n--- Current Holdings Analysis ---\n")
    results = []
    for code, pos in positions.items():
        name = pos.get('name', 'Unknown')
        industry = get_stock_industry(code)
        
        df = get_stock_daily_history(code)
        classification = stock_classifier.classify_stock(code, df)
        
        layer = classification['layer']
        stock_type = classification['type']
        
        # Advice based on expert opinion:
        # "防守型股可持，冲锋型股逢高减仓"
        if layer == LAYER_AGGRESSIVE:
            type_label = "冲锋型 (激进层)"
            advice = "⚠️ 专家建议：明日冲高减仓，注意高位分化风险。"
        elif layer == LAYER_CONSERVATIVE:
            type_label = "防守型 (稳健层)"
            advice = "✅ 专家建议：相对安全，仍可持股，关注5日线支撑。"
        else:
            type_label = "普通型"
            advice = "按原止损止盈位持有。"
            
        results.append({
            "代码": code,
            "名称": name,
            "行业": industry,
            "类型": type_label,
            "分数": classification['score'],
            "建议": advice,
            "特征": "; ".join(classification['reasons'][:2])
        })

    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))
    
    # Save to a temporary file for the summary
    df_results.to_csv("data/reports/held_stocks_analysis.csv", index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    analyze_held_stocks()
