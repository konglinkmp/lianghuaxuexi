import os
import logging
import json
from typing import Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

class ExpertAnalyzer:
    """
    AI 专家见解分析器
    将博主的文字见解转化为量化的情绪因子 (-1.0 到 1.0)
    """
    
    def __init__(self, model_type: str = "kimi"):
        """
        初始化分析器，默认优先使用 Kimi (余额较多)
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
            logger.warning(f"{model_type} API Key 未配置，专家见解分析将跳过")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def analyze_opinion(self, text: str) -> Dict:
        """
        分析专家见解文本
        
        Returns:
            Dict: {
                'sentiment_score': float,  # -1.0 到 1.0
                'summary': str,            # 核心观点总结
                'small_cap_risk': bool,    # 是否提到中小盘风险
                'action_advice': str       # 操作建议
            }
        """
        if not self.client or not text.strip():
            return {
                'sentiment_score': 0.0,
                'summary': '未提供见解或 AI 未配置',
                'small_cap_risk': False,
                'action_advice': '按原计划执行'
            }
            
        prompt = f"""
你是一位资深的 A 股策略分析师。请阅读以下财经博主的市场见解，并将其转化为量化的系统参数。

专家见解内容：
---
{text}
---

请从以下维度进行评估：
1. sentiment_score (情绪得分)：范围 -1.0 到 1.0。
   - -1.0: 极度悲观，建议空仓。
   - -0.5: 比较谨慎，建议减仓或收紧止损。
   - 0.0: 中性或观点不明确。
   - 0.5: 比较乐观，建议积极寻找机会。
   - 1.0: 极度乐观，建议满仓。
2. small_cap_risk (中小盘风险)：布尔值。如果博主提到了“中小盘诱多”、“小票回踩”、“风格切换到大盘”等，设为 true。
3. summary (核心观点)：用一句话总结博主的最核心观点（20字以内）。
4. action_advice (操作建议)：根据博主的话，给出一个具体的交易动作建议（20字以内）。

请严格按照以下 JSON 格式返回结果，不要包含任何其他文字：
{{
    "sentiment_score": float,
    "small_cap_risk": boolean,
    "summary": "...",
    "action_advice": "..."
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的 A 股策略量化助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"} if self.model_type == "deepseek" else None
            )
            
            content = response.choices[0].message.content
            # 清理可能存在的 markdown 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            result = json.loads(content)
            
            # 确保分数在范围内
            result['sentiment_score'] = max(-1.0, min(1.0, float(result.get('sentiment_score', 0.0))))
            return result
            
        except Exception as e:
            logger.error(f"AI 分析专家见解失败: {e}")
            return {
                'sentiment_score': 0.0,
                'summary': '分析失败',
                'small_cap_risk': False,
                'action_advice': '按原计划执行'
            }

# 创建全局实例
expert_analyzer = ExpertAnalyzer()
