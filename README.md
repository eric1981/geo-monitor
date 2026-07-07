<p align="center">
  <h1 align="center">🌐 GEO Monitor</h1>
</p>

<p align="center">
  AI 平台回答监控 · DeepSeek · 豆包 · 元宝
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/playwright-%E2%9C%93-2EAD33" alt="Playwright">
  <img src="https://img.shields.io/badge/sqlite-WAL-green" alt="SQLite">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

---

## 这是什么

定时在主流 AI 平台（DeepSeek、豆包、元宝）上查询预设问题，记录 AI 的回答和引用来源，追踪品牌/内容在 AI 搜索中的可见度变化。

## 平台

| 平台 | 技术方案 | 每问耗时 |
|------|---------|---------|
| DeepSeek | Playwright Chromium + stealth | ~20s |
| 豆包 | Chrome Extension + Native Messaging（真实浏览器） | ~90s |
| 元宝 | Playwright Chromium + stealth | ~20s |

> 豆包反 headless 检测极强，Playwright 无法使用（触发 CAPTCHA / 强制登出）。最终方案：Chrome 扩展 + Native Messaging，在真实浏览器中操作。

## 快速开始

```bash
cd ~/geo-monitor
uv venv && uv pip install -r requirements.txt
python3 monitor.py setup

# 登录各平台
python3 monitor.py login deepseek   # Playwright 浏览器
python3 monitor.py login yuanbao    # Playwright 浏览器
# 豆包：在 Chrome 中登录 doubao.com/chat 即可（需先加载扩展，见下方）

# 运行
python3 monitor.py run -p deepseek  # 单平台测试
python3 monitor.py run              # 全部平台
```

## 豆包扩展安装

```
1. 注册 Native Host：powershell -File "\\wsl$\Ubuntu-24.04\home\eric\geo-monitor\native-host\install.ps1"
2. Chrome → chrome://extensions → 加载 C:\Users\NINGMEI\geo-test-ext
3. Chrome 打开 doubao.com/chat 登录
```

## 命令

```
monitor.py setup              # 初始化数据库
monitor.py login [platform]   # 登录平台
monitor.py run [-p platform]  # 查询
monitor.py list [-n 20]       # 记录
monitor.py detail <id>        # 详情+引用
monitor.py history <qid>      # 历史
monitor.py add "问题" -g 组   # Agent 写入
monitor.py schedule           # 定时调度
```

## 项目结构

```
geo-monitor/
├── monitor.py              # CLI
├── config.yaml             # 平台+问题+调度
├── db.py + schema.sql      # SQLite
├── querier.py              # 调度器
├── adapters/
│   ├── deepseek_web.py     # DeepSeek (Playwright)
│   ├── doubao_ext.py       # 豆包 (Chrome Extension)
│   ├── yuanbao_web.py      # 元宝 (Playwright)
│   └── doubao_web.py       # 豆包 (Playwright, 已废弃)
├── doubao-ext/             # 豆包 Chrome 扩展
├── native-host/            # Native Messaging Bridge
│   ├── doubao_bridge.py    # 桥接服务
│   ├── doubao_cli.py       # CLI 接口
│   └── install.ps1         # Windows 安装
└── sessions/               # 浏览器 Profile
```

## License

MIT
