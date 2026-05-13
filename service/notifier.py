"""
=============================================================================
通知抽象层 - Notifier
=============================================================================

定义通知接口，与具体渠道解耦。
巡检或其他模块通过 Notifier.send() 发消息，不关心是钉钉、飞书还是邮件。

用法：
    from service.notifier import Notifier

    # 全局通知器，启动时初始化
    Notifier.init(type="dingtalk", ...)

    # 发消息
    Notifier.send("📊 数据巡检\n告警内容...")

    或（当未初始化时优雅降级）：
    notify = Notifier.INSTANCE
    if notify:
        notify.send("告警内容")

扩展：新增渠道时继承 BaseNotifier 即可
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("notifier")


# ──────────────────────────────────────────────
# 抽象基类
# ──────────────────────────────────────────────
class BaseNotifier(ABC):
    """通知渠道的抽象接口"""

    @abstractmethod
    def send(self, content: str, title: str = "") -> bool:
        """发送通知。返回 True 表示发送成功。"""
        ...


# ──────────────────────────────────────────────
# 空实现（静默丢弃，用于没有配置通知渠道时）
# ──────────────────────────────────────────────
class NullNotifier(BaseNotifier):
    def send(self, content: str, title: str = "") -> bool:
        logger.debug(f"[NullNotifier] 丢弃通知: {title or content[:50]}")
        return False


# ──────────────────────────────────────────────
# 日志通知（仅写入日志，用于本地开发/调试）
# ──────────────────────────────────────────────
class LogNotifier(BaseNotifier):
    def send(self, content: str, title: str = "") -> bool:
        logger.info(f"[通知] {title}\n{content}")
        return True


# ──────────────────────────────────────────────
# Notifier 入口
# ──────────────────────────────────────────────
class Notifier:
    """
    全局通知器。

    用法：
        # 初始化（应用启动时调用一次）
        Notifier.init("dingtalk", user_id="1830664110642027")

        # 或者在 init 中传入自定义 notifier
        Notifier.init(custom_notifier=MyNotifier())

        # 发消息
        Notifier.send("告警内容", title="数据采集告警")

        # 获取当前实例
        instance = Notifier.INSTANCE  # 可能为 None（未初始化时）
    """

    INSTANCE: Optional[BaseNotifier] = None

    @classmethod
    def init(cls, type: str = None, custom_notifier: BaseNotifier = None, **kwargs):
        """
        初始化全局通知器。

        Args:
            type: "dingtalk" | "log" | "null"，与 custom_notifier 二选一
            custom_notifier: 自定义通知器实例
            **kwargs: 传给特定类型的初始化参数
        """
        # 允许通过环境变量 NOTIFIER_TYPE 覆盖（方便部署时切换）
        import os
        env_type = os.getenv("NOTIFIER_TYPE", "").lower()
        if env_type:
            type = env_type

        if custom_notifier is not None:
            cls.INSTANCE = custom_notifier
        elif type == "dingtalk":
            from service.notifiers.dingtalk import DingtalkNotifier
            cls.INSTANCE = DingtalkNotifier(**kwargs)
        elif type == "log":
            cls.INSTANCE = LogNotifier()
        elif type == "null":
            cls.INSTANCE = NullNotifier()
        else:
            cls.INSTANCE = LogNotifier()
            logger.warning(f"未知通知类型 '{type}'，回退到 LogNotifier")

        logger.info(f"通知器初始化完成: {type or 'custom'}")

    @classmethod
    def send(cls, content: str, title: str = "通知") -> bool:
        """发送通知。如果未初始化则静默丢弃。"""
        if cls.INSTANCE is None:
            logger.warning("Notifier 未初始化，通知已丢弃")
            return False
        return cls.INSTANCE.send(content=content, title=title)
