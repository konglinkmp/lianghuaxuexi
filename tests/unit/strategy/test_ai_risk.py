import sys
import os
import json
from unittest.mock import MagicMock, patch

# 将项目根目录添加到路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'src'))

from quant.strategy.news_risk_analyzer import NewsRiskAnalyzer

def test_mock_ai_analysis():
    print("🚀 开始模拟 AI 风险分析测试...")
    
    # 模拟新闻数据
    mock_news = [
        {'date': '2026-01-07', 'title': '城建发展：关于收到监管工作函的公告', 'content': '公司收到证监会监管工作函...'},
        {'date': '2026-01-06', 'title': '城建发展：大股东拟减持5%股份', 'content': '大股东计划在未来6个月内减持...'}
    ]
    
    # 模拟 AI 响应
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "risk_level": "MEDIUM",
        "risk_reason": "大额减持+监管函",
        "details": "公司面临大股东大额减持压力，且收到监管函，短期存在不确定性。"
    })
    
    with patch('quant.strategy.news_risk_analyzer.get_stock_news', return_value=mock_news):
        with patch('openai.resources.chat.completions.Completions.create', return_value=mock_response):
            # 强制设置一个假的 API Key 以便初始化
            os.environ["DEEPSEEK_API_KEY"] = "sk-test"
            analyzer = NewsRiskAnalyzer(model_type="deepseek")
            
            result = analyzer.analyze_risk("600266", "城建发展")
            
            print("\n✅ 模拟测试结果:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            assert result['risk_level'] == "MEDIUM"
            assert "减持" in result['risk_reason']
            print("\n🎉 逻辑验证通过！")

if __name__ == "__main__":
    try:
        test_mock_ai_analysis()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
