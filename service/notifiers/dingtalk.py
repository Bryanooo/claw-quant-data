"""
=============================================================================
钉钉通知器
=============================================================================

通过 OpenClaw 的 message send 命令发送钉钉消息。
与 Notifier 抽象层解耦，新增其他渠道时只需创建一个新的 notifier 实现。

用法（不直接使用，通过 Notifier 入口）：
    from service.notifier import Notifier
    Notifier.init(type="dingtalk", user_id="1830664110642027")
"""

import json
import logging
import os
import subprocess

from service.notifier import BaseNotifier

logger = logging.getLogger("notifier.dingtalk")

_DEFAULT_USER_ID = os.getenv("DINGTALK_USER_ID", "1830664110642027")


class DingtalkNotifier(BaseNotifier):
    """钉钉通知器，复用 OpenClaw 的 message send 命令。"""

    def __init__(self, user_id: str = _DEFAULT_USER_ID):
        self.user_id = user_id

    def send(self, content: str, title: str = "通知") -> bool:
        """
        发送钉钉消息。

        Args:
            content: 消息正文
            title: 消息标题
        Returns:
            bool: 是否发送成功
        """
        full_content = f"**{title}**\n\n{content}"
        try:
            result = subprocess.run(
                ["openclaw", "message", "send",
                 "--channel", "clawdbot-dingtalk",
                 "--account", "default",
                 "-t", self.user_id,
                 "-m", full_content,
                 "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                resp = json.loads(result.stdout)
                if resp.get("payload", {}).get("result", {}).get("messageId"):
                    logger.info(f"✅ 钉钉消息已发送: {title}")
                    return True
                else:
                    logger.warning(f"钉钉消息可能未送达: {resp}")
                    return False
            else:
                logger.warning(f"openclaw message send 失败: {result.stderr[:200]}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("openclaw message send 超时")
            return False
        except Exception as e:
            logger.error(f"发送异常: {e}")
            return False
