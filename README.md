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

| 平台 | 技术方案 | 每问耗时 | macOS |
|------|---------|---------|-------|
| DeepSeek | Playwright Chromium + stealth | ~20s | ✅ 开箱即用 |
| 豆包 | Chrome Extension + Native Messaging | ~90s | ✅ 需安装扩展（[见下方](#macos-适配)） |
| 元宝 | Playwright Chromium + stealth | ~20s | ✅ 开箱即用 |

> 豆包反 headless 检测极强，Playwright 无法使用。最终方案：Chrome 扩展 + Native Messaging，在真实浏览器中操作。

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

### Windows/WSL

```powershell
powershell -File "\\wsl$\Ubuntu-24.04\home\eric\geo-monitor\native-host\install.ps1"
```
Chrome → `chrome://extensions` → 加载 `C:\Users\NINGMEI\geo-test-ext`

### macOS

```bash
bash native-host/install-macos.sh [extension_id]
```
Chrome → `chrome://extensions` → 加载 `doubao-ext/`

> 扩展 ID 每次加载解压扩展时会变化，需更新 manifest。Service Worker console 应显示 `Native host connected`。

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
│   ├── install.ps1         # Windows 安装
│   └── install-macos.sh    # macOS 安装
└── sessions/               # 浏览器 Profile

## macOS 适配

DeepSeek 和元宝（Playwright）开箱即用。豆包需要手动适配：

### 与 Windows/WSL 的差异

| 项 | Windows/WSL | macOS |
|----|------------|-------|
| Python 调用 | `wsl.exe -d ... -- python3` | 直接 `python3` |
| Native Host 注册 | Registry (`HKCU\...`) | plist 文件 (`~/Library/.../NativeMessagingHosts/`) |
| Native Host 脚本 | `.bat` | `.sh`（需 `chmod +x`） |
| Playwright 浏览器 | 内置 Chromium | 内置 Chromium 或 `channel: "chrome"` |

### 注意事项

1. **首次运行**：`playwright install chromium`
2. **权限**：`.sh` 脚本需要 `chmod +x`，可能弹 Gatekeeper
3. **扩展 ID 变化**：每次加载解压扩展，ID 随机变。需重新跑 `install-macos.sh <新ID>`
4. **Chrome 完全退出**：Cmd+Q，不是关窗口。改 Native Host 后必须重启 Chrome
5. **会话不能跨机器复制**：`sessions/` 下的 Chrome Profile 加密绑定本机

## License

MIT
