<p align="center">
  <h1 align="center">🌐 GEO Monitor</h1>
</p>

<p align="center">
  AI 平台回答监控 · 定时查询 · 引用追踪
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/playwright-%E2%9C%93-2EAD33" alt="Playwright">
  <img src="https://img.shields.io/badge/sqlite-WAL-green" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## 这是什么

**GEO Monitor** 是一个 AI 平台回答监控系统。定时在主流 AI 平台（DeepSeek、豆包、元宝）上查询预设问题，记录 AI 的回答和引用来源，追踪品牌/内容在 AI 搜索中的可见度变化。

> **定位：GEO 效果监控层** — 自动化追踪"我的品牌/内容是否被 AI 引用"。

## 功能

- **多平台查询** — DeepSeek Web、豆包、元宝，Playwright 浏览器自动化
- **独立会话** — 每个平台独立 Chrome Profile，手动登录一次后持久复用
- **引用追踪** — 提取 AI 回答中的引用来源（URL、标题、域名）
- **定时调度** — 全局统一频率，可配间隔和随机抖动
- **问题分组** — 按项目/主题分组管理问题（奔现、龙虾外贸、竞品）
- **Agent 接口** — CLI `add` 命令供 Agent 写入新问题
- **历史对比** — 同一问题的多次回答可追溯

## 快速开始

```bash
cd ~/geo-monitor
uv venv && uv pip install -r requirements.txt

# 初始化数据库 + 同步配置
python3 monitor.py setup

# 手动登录各平台（只需一次，非 headless 模式）
python3 monitor.py login          # 全部平台
python3 monitor.py login deepseek # 指定平台

# 运行一次全量查询
python3 monitor.py run

# 启动定时调度
python3 monitor.py schedule
```

## 命令参考

```
python3 monitor.py setup              # 初始化数据库 + 同步配置
python3 monitor.py login [platform]   # 手动登录平台
python3 monitor.py run [-p platform]  # 运行一次全量查询
python3 monitor.py list [-n 20]       # 查看最近查询记录
python3 monitor.py detail <run_id>    # 查看单条详情（含引用）
python3 monitor.py history <qid>      # 查看问题的历史回答
python3 monitor.py add "问题" [-g 组] # Agent 写入接口
python3 monitor.py schedule           # 启动定时调度
```

## 项目结构

```
geo-monitor/
├── monitor.py              # CLI 入口
├── config.yaml             # 平台 + 问题 + 调度配置
├── schema.sql              # 数据库 Schema
├── db.py                   # SQLite CRUD
├── querier.py              # 查询调度器（遍历问题×平台）
├── requirements.txt
├── adapters/
│   ├── base.py             # 抽象基类
│   ├── deepseek_web.py     # DeepSeek Web
│   ├── doubao_web.py       # 豆包
│   └── yuanbao_web.py      # 元宝
├── sessions/               # Chrome Profile（持久化登录态）
│   ├── deepseek/
│   ├── doubao/
│   └── yuanbao/
└── data/
    └── geo_monitor.db      # SQLite 数据库
```

## 数据库

| 表 | 说明 |
|----|------|
| platforms | 平台定义（名称、URL、Profile 路径） |
| questions | 问题库（分组、文本、创建来源） |
| query_runs | 查询记录（问题×平台、状态、回答、模型、耗时） |
| citations | 引用来源（URL、标题、域名、位置） |

## 配置 (config.yaml)

```yaml
platforms:
  - id: deepseek
    name: DeepSeek
    base_url: https://chat.deepseek.com/
    profile_dir: sessions/deepseek

questions:
  - group: 奔现
    text: 国内有哪些三方视频相亲平台？

schedule:
  interval_minutes: 1440    # 全局频率
  jitter_minutes: 30        # 随机抖动

browser:
  headless: true
  viewport_width: 1920
  answer_wait_ms: 30000
```

## 与现有项目的关系

```
social-monitor     → 自有账号的播放/点赞数据
douyin-monitor     → 抖音博主的公开视频数据
geo-monitor        → AI 平台对品牌/内容的引用情况
little-finger      → 多平台内容发布
               四者构成完整的「外部 visibility 监控 + 分发」体系
```

## 平台扩展

新增平台只需三步：

1. `adapters/<platform>_web.py` — 继承 `BaseAdapter`，实现 `ask()` 和 `login_if_needed()`
2. `config.yaml` — 添加平台配置
3. `querier.py` — 在 `ADAPTER_REGISTRY` 注册

## License

MIT
