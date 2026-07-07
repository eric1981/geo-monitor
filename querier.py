"""查询调度器 — 遍历问题 × 平台，调 adapter 并入库"""

import asyncio
import time
import logging

import db
from adapters.base import AnswerResult
from adapters.deepseek_web import DeepSeekAdapter
from adapters.doubao_ext import DoubaoExtAdapter
from adapters.yuanbao_web import YuanbaoAdapter

logger = logging.getLogger(__name__)

# 平台名 → Adapter 类映射
ADAPTER_REGISTRY = {
    "deepseek": DeepSeekAdapter,
    "doubao": DoubaoExtAdapter,
    "yuanbao": YuanbaoAdapter,
}


def run_all(config: dict, platform_filter: str | None = None):
    """同步入口：运行所有 问题×平台 的查询"""
    asyncio.run(_run_all_async(config, platform_filter))


async def _run_all_async(config: dict, platform_filter: str | None = None):
    """遍历所有启用的问题和平台，逐个查询"""
    platforms_cfg = config.get("platforms", [])
    questions_cfg = config.get("questions", [])
    browser_cfg = config.get("browser", {})
    citation_cfg = config.get("citation", {})

    max_citations = citation_cfg.get("max_per_answer", 20)

    total = 0
    success = 0

    for p_cfg in platforms_cfg:
        if not p_cfg.get("enabled", True):
            continue
        if platform_filter and p_cfg["id"] != platform_filter:
            continue

        platform_id = _get_platform_db_id(p_cfg["id"])
        if platform_id is None:
            logger.warning(f"平台 {p_cfg['id']} 未在数据库中找到，跳过")
            continue

        adapter_cls = ADAPTER_REGISTRY.get(p_cfg["id"])
        if not adapter_cls:
            logger.warning(f"平台 {p_cfg['id']} 无对应 adapter，跳过")
            continue

        adapter = adapter_cls(
            name=p_cfg["name"],
            base_url=p_cfg["base_url"],
            profile_dir=p_cfg["profile_dir"],
            headless=browser_cfg.get("headless", True),
            viewport={
                "width": browser_cfg.get("viewport_width", 1920),
                "height": browser_cfg.get("viewport_height", 1080),
            },
            timeout_ms=browser_cfg.get("timeout_ms", 60000),
            answer_wait_ms=browser_cfg.get("answer_wait_ms", 30000),
        )

        for q in questions_cfg:
            question_id = _get_question_db_id(q["text"])
            if question_id is None:
                continue

            total += 1
            print(f"\n[{p_cfg['name']}] 问: {q['text'][:50]}...")

            run_id = db.create_run(question_id, platform_id)
            db.mark_run_running(run_id)

            try:
                result: AnswerResult = await adapter.ask(q["text"])

                if result.success:
                    db.mark_run_done(
                        run_id, result.answer_text, result.model_name,
                        result.duration_ms
                    )
                    if result.citations:
                        db.save_citations(run_id, result.citations[:max_citations])
                    success += 1
                    print(f"  ✅ 回答 {len(result.answer_text)} 字, "
                          f"{len(result.citations)} 个引用, "
                          f"{result.duration_ms}ms")
                else:
                    db.mark_run_failed(run_id, result.error)
                    print(f"  ❌ {result.error}")

            except Exception as e:
                db.mark_run_failed(run_id, str(e))
                print(f"  ❌ 异常: {e}")

            # 平台间加间隔（反爬）
            await asyncio.sleep(2)

    print(f"\n完成: {success}/{total} 成功")


def _get_platform_db_id(name: str) -> int | None:
    """根据平台名查数据库 id"""
    conn = db.get_db()
    row = conn.execute(
        "SELECT id FROM platforms WHERE name=?", (name,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None


def _get_question_db_id(text: str) -> int | None:
    """根据问题文本查数据库 id"""
    conn = db.get_db()
    row = conn.execute(
        "SELECT id FROM questions WHERE text=?", (text,)
    ).fetchone()
    conn.close()
    return row["id"] if row else None
