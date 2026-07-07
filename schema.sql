-- geo-monitor 数据库 Schema
-- AI 平台回答监控系统

CREATE TABLE IF NOT EXISTS platforms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,          -- deepseek / doubao / yuanbao
    display_name TEXT NOT NULL,                -- DeepSeek / 豆包 / 元宝
    base_url    TEXT NOT NULL,                 -- 聊天页面 URL
    profile_dir TEXT NOT NULL,                 -- Chrome profile 目录
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL DEFAULT 'default',  -- 问题分组：奔现/龙虾/竞品
    text        TEXT NOT NULL,                    -- 问题文本
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_by  TEXT DEFAULT 'manual',            -- manual / agent:<name>
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(text)                                   -- 去重
);

CREATE TABLE IF NOT EXISTS query_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id   INTEGER NOT NULL REFERENCES questions(id),
    platform_id   INTEGER NOT NULL REFERENCES platforms(id),
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending/running/done/failed
    answer_text   TEXT,
    model_name    TEXT,                             -- AI 模型名称（从页面提取）
    error_message TEXT,
    duration_ms   INTEGER,
    query_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_runs_question ON query_runs(question_id);
CREATE INDEX IF NOT EXISTS idx_runs_platform ON query_runs(platform_id);
CREATE INDEX IF NOT EXISTS idx_runs_query_at ON query_runs(query_at);

CREATE TABLE IF NOT EXISTS citations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES query_runs(id),
    url         TEXT,
    title       TEXT,
    domain      TEXT,
    position    INTEGER,               -- 第几个引用（从 0 开始）
    snippet     TEXT,                   -- 截取的上下文
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_citations_run ON citations(run_id);
