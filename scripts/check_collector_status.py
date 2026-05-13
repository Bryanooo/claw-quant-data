"""=============================================================================
采集任务巡检脚本 - 检查失败的、超时的、缺失的任务
=============================================================================

用 OpenClaw cron 定时触发，发现异常时通过 announce 模式通知钉钉。

用法：
  python3.11 scripts/check_collector_status.py

输出格式（多行字符串）：
  如果是巡检时没有发现问题，输出空字符串或"✅ 所有任务正常"
  如果发现问题，输出要通知的内容（cron announce 会直接发给用户）

安装（一次性）：
  openclaw cron add \\
    --name "采集任务巡检" \\
    --cron "*/15 6-22 * * 1-5" \\
    --tz "Asia/Shanghai" \\
    --session isolated \\
    --message "$(python3.11 scripts/check_collector_status.py)" \\
    --announce \\
    --channel "clawdbot-dingtalk" \\
    --to "1830664110642027"
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta, timezone
from service.run_tracker import check_timeout_tasks, count_failed_tasks, get_latest_runs


def check(alert_on_fail: int = 1) -> str:
    """
    执行巡检，返回通知内容。
    如果一切正常，返回空字符串（cron 不会发送空消息）。
    """
    now = datetime.now(timezone.utc) + timedelta(hours=8)
    today = now.strftime("%Y-%m-%d %H:%M")
    messages = []

    # 1. 检查 timeout 任务
    timed_out = check_timeout_tasks(timeout_minutes=45)
    for t in timed_out:
        started = t["started_at"].strftime("%H:%M") if t["started_at"] else "?"
        messages.append(f"⚠️ 超时：{t['task_name']}（{started} 启动，已超 45 分钟）")

    # 2. 检查最近 6 小时的失败任务
    failed = count_failed_tasks(since_hours=6)
    if failed:
        total_fails = sum(r["cnt"] for r in failed)
        if total_fails >= alert_on_fail:
            fail_list = "\n".join(
                f"  · {r['task_name']} → 失败 {r['cnt']} 次"
                for r in failed
            )
            messages.append(f"❌ 任务失败告警（近6h）:\n{fail_list}")

    # 3. 检查最近一条 daily 运行是否正常（每日数据核心）
    daily_runs = get_latest_runs(task_id="daily_daily", limit=1)
    if daily_runs:
        r = daily_runs[0]
        if r["status"] == "failed":
            messages.append(f"🚨 昨日日线行情(daily)采集失败！请尽快处理")
        elif r["status"] == "timeout":
            messages.append(f"⚠️ 昨日日线行情(daily)采集超时")

    # 4. 检查 bak_basic 盘后运行
    bak_runs = get_latest_runs(task_id="bak_basic_daily", limit=1)
    if bak_runs:
        r = bak_runs[0]
        if r["status"] == "failed":
            messages.append(f"⚠️ bak_basic 盘后采集失败")

    # 5. 检查今日交易日是否有核心任务未触发
    # （可做但先简单一点）

    if messages:
        header = f"📊 数据巡检报告 ({today})\n{'─'*30}\n"
        return header + "\n".join(messages)

    return ""


if __name__ == "__main__":
    result = check()
    if result:
        print(result)
    else:
        print("✅ 所有采集任务正常")
