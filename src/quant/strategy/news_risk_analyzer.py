import os
import logging
import json
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from ..core.data_fetcher import get_stock_news

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

class NewsRiskAnalyzer:
    """
    AI 驱动的新闻与公告风险分析器
    """
    
    def __init__(self, model_type: str = "deepseek"):
        """
        初始化分析器
        
        Args:
            model_type: 'deepseek' 或 'kimi'
        """
        self.model_type = model_type
        
        if model_type == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            self.model_name = "deepseek-chat"
        elif model_type == "kimi":
            api_key = os.getenv("KIMI_API_KEY")
            base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
            self.model_name = "moonshot-v1-8k"
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")
            
        if not api_key:
            logger.warning(f"{model_type} API Key 未配置，AI 风险分析将跳过")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def analyze_risk(self, symbol: str, name: str) -> Dict:
        """
        分析特定股票的风险
        
        Returns:
            Dict: {
                'risk_level': 'LOW' | 'MEDIUM' | 'HIGH',
                'risk_reason': str,
                'details': str
            }
        """
        if not self.client:
            return {'risk_level': 'LOW', 'risk_reason': 'AI 未配置', 'details': ''}
            
        # 获取新闻
        news = get_stock_news(symbol, limit=5)
        if not news:
            return {'risk_level': 'LOW', 'risk_reason': '无近期新闻公告', 'details': ''}
            
        # 构造 Prompt
        news_text = "\n".join([f"- {n['date']} {n['title']}: {n['content'][:100]}..." for n in news])
        
        prompt = f"""
你是一位专业的 A 股分析师。请分析以下股票最近的新闻和公告，评估其潜在风险。

股票：{name} ({symbol})
近期动态：
{news_text}

请特别注意：用户已明确要求**排除房地产**及相关博主提到的**夕阳产业**。

请从以下维度评估风险等级：
1. HIGH (高风险)：立案调查、财务造假、大股东爆仓、严重业绩变脸、退市风险，**或者属于房地产及夕阳行业**。
2. MEDIUM (中风险)：大额减持计划、监管函、异动停牌风险、行业重大利空。
3. LOW (低风险)：一般性减持、正常业务波动、无明显负面消息。

请严格按照以下 JSON 格式返回结果，不要包含任何其他文字：
{{
    "risk_level": "HIGH/MEDIUM/LOW",
    "risk_reason": "核心风险原因简述（15字以内）",
    "details": "详细风险分析（50字以内）"
}}
"""

        try:
            # 对于 DeepSeek，我们可以使用 json_object 模式
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融风险评估助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"} if self.model_type == "deepseek" else None
            )
            
            content = response.choices[0].message.content
            # 简单清理可能存在的 markdown 代码块
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
                
            result = json.loads(content)
            return result
        except Exception as e:
            logger.error(f"AI 分析 {symbol} 风险失败: {e}")
            return {'risk_level': 'LOW', 'risk_reason': '分析失败', 'details': str(e)}

# 创建全局实例
news_risk_analyzer = NewsRiskAnalyzer()


if __name__ == "__main__":
    # 简单测试
    logging.basicConfig(level=logging.INFO)
    res = news_risk_analyzer.analyze_risk("600266", "城建发展")
    print(json.dumps(res, indent=2, ensure_ascii=False))
