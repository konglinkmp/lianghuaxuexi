import sys
import os
import json
import logging

# 将项目根目录添加到路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'src'))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from quant.strategy.news_risk_analyzer import NewsRiskAnalyzer

def test_real_ai_analysis():
    print("🚀 开始真实环境 AI 风险分析测试 (DeepSeek)...")
    
    analyzer = NewsRiskAnalyzer(model_type="deepseek")
    
    # 测试一只近期有热度的股票
    symbol = "600266"
    name = "城建发展"
    
    print(f"🔍 正在分析: {name} ({symbol})...")
    result = analyzer.analyze_risk(symbol, name)
    
    print("\n✅ 真实测试结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get('risk_level'):
        print("\n🎉 API 调用成功！AI 风险分析模块工作正常。")
    else:
        print("\n❌ API 调用可能存在问题，未返回预期结果。")

if __name__ == "__main__":
    test_real_ai_analysis()
