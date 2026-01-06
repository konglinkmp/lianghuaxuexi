"""
消息推送模块
支持微信、钉钉、企业微信等渠道推送交易信号
"""

import json
import requests
from datetime import datetime
from typing import Optional, List, Dict
import hashlib
import hmac
import base64
import time
import urllib.parse


class NotificationConfig:
    """通知配置"""
    
    def __init__(self, config_file: str = "config/notification_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """加载配置"""
        default_config = {
            'enabled': False,
            'channels': {
                'dingtalk': {
                    'enabled': False,
                    'webhook': '',
                    'secret': ''  # 可选，用于签名
                },
                'wecom': {  # 企业微信
                    'enabled': False,
                    'webhook': ''
                },
                'server_chan': {  # Server酱（微信推送）
                    'enabled': False,
                    'send_key': ''
                },
                'bark': {  # Bark（iOS推送）
                    'enabled': False,
                    'server': 'https://api.day.app',
                    'device_key': ''
                }
            }
        }
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # 创建默认配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            print(f"[信息] 已创建通知配置文件: {self.config_file}")
            print("[提示] 请编辑配置文件，填入您的webhook地址后重新运行")
            return default_config
        except Exception as e:
            print(f"[警告] 加载通知配置失败: {e}")
            return default_config
    
    def save_config(self):
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)


class DingTalkNotifier:
    """钉钉机器人通知"""
    
    def __init__(self, webhook: str, secret: str = ""):
        self.webhook = webhook
        self.secret = secret
    
    def _get_sign(self) -> str:
        """生成签名"""
        if not self.secret:
            return ""
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, 
                            digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return f"&timestamp={timestamp}&sign={sign}"
    
    def send(self, title: str, content: str) -> bool:
        """
        发送钉钉消息
        
        Args:
            title: 消息标题
            content: 消息内容（支持Markdown）
            
        Returns:
            bool: 是否发送成功
        """
        if not self.webhook:
            return False
        
        url = self.webhook + self._get_sign()
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}"
            }
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                print(f"[警告] 钉钉发送失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"[警告] 钉钉发送异常: {e}")
            return False


class WeComNotifier:
    """企业微信机器人通知"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send(self, title: str, content: str) -> bool:
        """
        发送企业微信消息
        
        Args:
            title: 消息标题
            content: 消息内容（支持Markdown）
            
        Returns:
            bool: 是否发送成功
        """
        if not self.webhook:
            return False
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n{content}"
            }
        }
        
        try:
            response = requests.post(self.webhook, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                return True
            else:
                print(f"[警告] 企业微信发送失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            print(f"[警告] 企业微信发送异常: {e}")
            return False


class ServerChanNotifier:
    """Server酱通知（微信推送）"""
    
    def __init__(self, send_key: str):
        self.send_key = send_key
        self.url = f"https://sctapi.ftqq.com/{send_key}.send"
    
    def send(self, title: str, content: str) -> bool:
        """
        发送Server酱消息
        
        Args:
            title: 消息标题
            content: 消息内容（支持Markdown）
            
        Returns:
            bool: 是否发送成功
        """
        if not self.send_key:
            return False
        
        data = {
            "title": title,
            "desp": content
        }
        
        try:
            response = requests.post(self.url, data=data, timeout=10)
            result = response.json()
            if result.get('code') == 0:
                return True
            else:
                print(f"[警告] Server酱发送失败: {result.get('message')}")
                return False
        except Exception as e:
            print(f"[警告] Server酱发送异常: {e}")
            return False


class BarkNotifier:
    """Bark通知（iOS推送）"""
    
    def __init__(self, server: str, device_key: str):
        self.server = server.rstrip('/')
        self.device_key = device_key
    
    def send(self, title: str, content: str) -> bool:
        """
        发送Bark消息
        
        Args:
            title: 消息标题
            content: 消息内容
            
        Returns:
            bool: 是否发送成功
        """
        if not self.device_key:
            return False
        
        url = f"{self.server}/{self.device_key}/{urllib.parse.quote(title)}/{urllib.parse.quote(content)}"
        
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            if result.get('code') == 200:
                return True
            else:
                print(f"[警告] Bark发送失败: {result.get('message')}")
                return False
        except Exception as e:
            print(f"[警告] Bark发送异常: {e}")
            return False


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, config_file: str = "config/notification_config.json"):
        self.config = NotificationConfig(config_file)
        self.notifiers = self._init_notifiers()
    
    def _init_notifiers(self) -> List:
        """初始化通知器"""
        notifiers = []
        channels = self.config.config.get('channels', {})
        
        # 钉钉
        dingtalk = channels.get('dingtalk', {})
        if dingtalk.get('enabled') and dingtalk.get('webhook'):
            notifiers.append(DingTalkNotifier(
                dingtalk['webhook'],
                dingtalk.get('secret', '')
            ))
        
        # 企业微信
        wecom = channels.get('wecom', {})
        if wecom.get('enabled') and wecom.get('webhook'):
            notifiers.append(WeComNotifier(wecom['webhook']))
        
        # Server酱
        server_chan = channels.get('server_chan', {})
        if server_chan.get('enabled') and server_chan.get('send_key'):
            notifiers.append(ServerChanNotifier(server_chan['send_key']))
        
        # Bark
        bark = channels.get('bark', {})
        if bark.get('enabled') and bark.get('device_key'):
            notifiers.append(BarkNotifier(
                bark.get('server', 'https://api.day.app'),
                bark['device_key']
            ))
        
        return notifiers
    
    def send_all(self, title: str, content: str) -> int:
        """
        发送消息到所有启用的渠道
        
        Args:
            title: 消息标题
            content: 消息内容
            
        Returns:
            int: 成功发送的渠道数
        """
        if not self.config.config.get('enabled', False):
            return 0
        
        success_count = 0
        for notifier in self.notifiers:
            if notifier.send(title, content):
                success_count += 1
        
        return success_count
    
    def send_trading_plan(self, plan_df) -> int:
        """
        发送交易计划
        
        Args:
            plan_df: 交易计划DataFrame
            
        Returns:
            int: 成功发送的渠道数
        """
        if plan_df.empty:
            return 0
        
        title = f"📋 量化交易信号 ({datetime.now().strftime('%m-%d')})"
        
        content_lines = [
            f"**共 {len(plan_df)} 只股票符合买入条件**",
            "",
            "| 股票 | 现价 | 止损 | 止盈 |",
            "|------|------|------|------|"
        ]

        if "风格基准权重" in plan_df.columns:
            weight_text = plan_df["风格基准权重"].iloc[0]
            if isinstance(weight_text, str) and weight_text:
                content_lines.insert(1, f"**风格基准权重**：{weight_text}")
                content_lines.insert(2, "")
        
        for _, row in plan_df.head(10).iterrows():  # 最多显示10只
            content_lines.append(
                f"| {row['名称']} | ¥{row['收盘价']} | ¥{row['止损价']} | ¥{row['止盈价']} |"
            )
        
        if len(plan_df) > 10:
            content_lines.append(f"\n*...还有 {len(plan_df) - 10} 只股票，请查看完整报告*")
        
        content_lines.append(f"\n⚠️ 以上仅供参考，不构成投资建议")
        
        return self.send_all(title, "\n".join(content_lines))
    
    def send_alert(self, alert_type: str, message: str) -> int:
        """
        发送警报
        
        Args:
            alert_type: 警报类型（如 'stop_loss', 'take_profit', 'drawdown'）
            message: 警报消息
            
        Returns:
            int: 成功发送的渠道数
        """
        type_emoji = {
            'stop_loss': '🔴 止损提醒',
            'take_profit': '🟢 止盈提醒',
            'drawdown': '⚠️ 回撤警告',
            'market_risk': '📉 大盘风险',
            'buy_signal': '📈 买入信号'
        }
        
        title = type_emoji.get(alert_type, '📢 交易提醒')
        return self.send_all(title, message)


# 创建全局实例
notification_manager = NotificationManager()


if __name__ == "__main__":
    # 测试
    print("=== 消息推送模块测试 ===\n")
    
    manager = NotificationManager()
    
    print(f"配置文件: {manager.config.config_file}")
    print(f"通知是否启用: {manager.config.config.get('enabled', False)}")
    print(f"已配置的通知渠道数: {len(manager.notifiers)}")
    
    if not manager.notifiers:
        print("\n[提示] 未配置任何通知渠道")
        print("请编辑 config/notification_config.json 文件：")
        print("1. 将 'enabled' 设为 true")
        print("2. 配置至少一个推送渠道（钉钉/企业微信/Server酱/Bark）")
    else:
        # 发送测试消息
        print("\n发送测试消息...")
        title = "🧪 测试消息"
        content = f"这是一条测试消息\n\n发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        success = manager.send_all(title, content)
        print(f"成功发送到 {success} 个渠道")
