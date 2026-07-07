#!/usr/bin/env python3
"""geo-monitor CLI — AI 平台回答监控系统

用法:
  python3 monitor.py setup              # 初始化数据库 + 同步配置
  python3 monitor.py login [platform]   # 手动登录指定平台（或全部）
  python3 monitor.py run                # 运行一次全量查询
  python3 monitor.py run -p deepseek    # 只查询指定平台
  python3 monitor.py list               # 查看最近查询记录
  python3 monitor.py detail <run_id>    # 查看单条查询详情（含引用）
  python3 monitor.py history <qid>      # 查看某个问题的历史回答
  python3 monitor.py add "问题文本" [-g 分组]  # Agent 写入接口
  python3 monitor.py schedule           # 启动定时调度
"""

import argparse
import asyncio
import sys
import yaml
from pathlib import Path

import db
from querier import run_all

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── 命令 ──

def cmd_setup():
    """初始化数据库 + 同步配置中的平台和问题"""
    db.init_db()
    config = load_config()
    db.sync_platforms(config.get("platforms", []))
    db.sync_questions(config.get("questions", []))
    print("✅ 数据库已初始化，平台和问题已同步")


def cmd_login(platform_id: str | None = None):
    """打开浏览器让用户手动登录"""
    config = load_config()

    async def _login():
        for p_cfg in config.get("platforms", []):
            if not p_cfg.get("enabled", True):
                continue
            if platform_id and p_cfg["id"] != platform_id:
                continue

            print(f"\n{'='*50}")
            print(f"登录 {p_cfg['name']} ({p_cfg['id']})")
            print(f"{'='*50}")

            adapter_cls = None
            if p_cfg["id"] == "deepseek":
                from adapters.deepseek_web import DeepSeekAdapter
                adapter_cls = DeepSeekAdapter
            elif p_cfg["id"] == "doubao":
                from adapters.doubao_ext import DoubaoExtAdapter
                adapter_cls = DoubaoExtAdapter
            elif p_cfg["id"] == "yuanbao":
                from adapters.yuanbao_web import YuanbaoAdapter
                adapter_cls = YuanbaoAdapter

            if adapter_cls:
                browser_cfg = config.get("browser", {})
                adapter = adapter_cls(
                    name=p_cfg["name"],
                    base_url=p_cfg["base_url"],
                    profile_dir=p_cfg["profile_dir"],
                    headless=False,
                    viewport={
                        "width": browser_cfg.get("viewport_width", 1920),
                        "height": browser_cfg.get("viewport_height", 1080),
                    },
                    timeout_ms=browser_cfg.get("timeout_ms", 60000),
                )
                ok = await adapter.login_if_needed()
                if not ok:
                    print(f"⚠️ {p_cfg['name']} 登录未完成")

    asyncio.run(_login())


def cmd_run(platform_filter: str | None = None):
    """运行一次全量查询"""
    config = load_config()
    db.init_db()

    # 确保平台和问题已同步
    db.sync_platforms(config.get("platforms", []))
    db.sync_questions(config.get("questions", []))

    run_all(config, platform_filter)


def cmd_list(limit: int = 20):
    """查看最近查询记录"""
    rows = db.get_latest_runs(limit)
    if not rows:
        print("暂无查询记录")
        return

    print(f"{'ID':<5} {'平台':<8} {'状态':<6} {'问题':<40} {'时间'}")
    print("-" * 90)
    for r in rows:
        status_icon = {"done": "✅", "failed": "❌", "running": "⏳", "pending": "⬜"}.get(
            r["status"], "❓"
        )
        text = (r["question_text"] or "")[:38]
        time_str = (r["query_at"] or "")[:16]
        print(f"{r['id']:<5} {r['platform_name']:<8} {status_icon:<6} {text:<40} {time_str}")


def cmd_detail(run_id: int):
    """查看单条查询详情"""
    detail = db.get_run_detail(run_id)
    if not detail:
        print(f"未找到查询记录: {run_id}")
        return

    print(f"平台: {detail['platform_name']}")
    print(f"问题: {detail['question_text']}")
    print(f"分组: {detail['group_name']}")
    print(f"模型: {detail['model_name']}")
    print(f"状态: {detail['status']}")
    print(f"耗时: {detail['duration_ms']}ms")
    print(f"时间: {detail['query_at']}")
    print(f"\n{'='*60}")
    print("回答:")
    print(detail.get("answer_text", "(空)"))
    print(f"\n{'='*60}")
    print(f"引用来源 ({len(detail.get('citations', []))} 条):")
    for c in detail.get("citations", []):
        print(f"  [{c['position']}] {c['title'][:50]}")
        print(f"      {c['url']}")


def cmd_history(question_id: int, limit: int = 10):
    """查看某个问题的历史回答"""
    rows = db.get_question_history(question_id, limit)
    if not rows:
        print(f"问题 {question_id} 暂无查询记录")
        return

    for r in rows:
        text = (r["answer_text"] or "")[:80]
        print(f"[{r['query_at']}] {r['platform_name']}: {text}...")


def cmd_add(text: str, group: str = "default", created_by: str = "manual"):
    """Agent 写入接口：添加问题"""
    qid = db.add_question(text, group, created_by)
    print(f"✅ 问题已添加 (id={qid}): [{group}] {text}")


def cmd_schedule():
    """启动定时调度"""
    import random
    import time
    import subprocess

    config = load_config()
    schedule_cfg = config.get("schedule", {})
    interval_min = schedule_cfg.get("interval_minutes", 1440)
    jitter_min = schedule_cfg.get("jitter_minutes", 30)

    print(f"定时调度已启动: 每 {interval_min} 分钟 (±{jitter_min} 分钟抖动)")
    print("按 Ctrl+C 停止")

    script_path = Path(__file__).resolve()

    try:
        while True:
            jitter = random.randint(-jitter_min, jitter_min)
            wait_seconds = (interval_min + jitter) * 60
            next_run = time.strftime("%Y-%m-%d %H:%M:%S",
                                     time.localtime(time.time() + wait_seconds))
            print(f"\n下次运行: {next_run}")

            time.sleep(wait_seconds)

            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始采集...")
            try:
                subprocess.run(
                    [sys.executable, str(script_path), "run"],
                    check=False, timeout=interval_min * 60
                )
            except subprocess.TimeoutExpired:
                print("⚠️ 采集超时")
            except Exception as e:
                print(f"⚠️ 采集异常: {e}")

    except KeyboardInterrupt:
        print("\n调度已停止")


# ── 入口 ──

def main():
    parser = argparse.ArgumentParser(
        description="geo-monitor — AI 平台回答监控",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="初始化数据库 + 同步配置")

    login_p = sub.add_parser("login", help="手动登录平台")
    login_p.add_argument("platform", nargs="?", help="平台 ID (deepseek/doubao/yuanbao)，不指定则全部")

    run_p = sub.add_parser("run", help="运行一次全量查询")
    run_p.add_argument("-p", "--platform", help="指定平台 (deepseek/doubao/yuanbao)")

    list_p = sub.add_parser("list", help="查看最近查询记录")
    list_p.add_argument("-n", "--limit", type=int, default=20, help="显示条数")

    detail_p = sub.add_parser("detail", help="查看单条查询详情")
    detail_p.add_argument("run_id", type=int)

    history_p = sub.add_parser("history", help="查看问题的历史回答")
    history_p.add_argument("qid", type=int, help="问题 ID")
    history_p.add_argument("-n", "--limit", type=int, default=10)

    add_p = sub.add_parser("add", help="添加问题 (Agent 写入接口)")
    add_p.add_argument("text", help="问题文本")
    add_p.add_argument("-g", "--group", default="default", help="分组名")

    sub.add_parser("schedule", help="启动定时调度")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup()
    elif args.command == "login":
        cmd_login(args.platform)
    elif args.command == "run":
        cmd_run(args.platform)
    elif args.command == "list":
        cmd_list(args.limit)
    elif args.command == "detail":
        cmd_detail(args.run_id)
    elif args.command == "history":
        cmd_history(args.qid, args.limit)
    elif args.command == "add":
        cmd_add(args.text, args.group)
    elif args.command == "schedule":
        cmd_schedule()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
