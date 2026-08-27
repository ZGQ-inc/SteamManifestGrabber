# Steam Manifest Grabber (Steam清单提取工具)

<p align="center">
  <img src="https://img.shields.io/badge/Version-v1.10-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Language-C%23%20%7C%20Python%203-blue.svg" alt="Languages">
  <img src="https://img.shields.io/badge/.NET-9.0%20Desktop%20Runtime-purple.svg" alt=".NET 9">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20Pip%20(Pure%20StdLib)-success.svg" alt="Zero Pip Dependencies">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-green.svg" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg" alt="License">
</p>

> **跨平台、免客户端挂载的 Steam 游戏底层清单（Manifest）与解密密钥（DecryptionKey）一键抓取、整理归档与 Lua 生成工具。**

## 📖 项目背景

以往社区常用的第三方 Go 语言提取工具因 SteamUI 底层网络协议调整而彻底报错失效且停止维护。

**Steam Manifest Grabber** 基于活跃维护的 [SteamKit2](https://github.com/SteamRE/SteamKit) 协议库与魔改版 [DepotDownloader](https://github.com/ZGQ-inc/DepotDownloader) 底座全新自研，无需在后台开启笨重的 Steam 官方客户端，直接与 Steam 官方服务器通信获取清单与通常被加密隐藏的 `DecryptionKey (解密密钥)`，并由 Python 脚本实现全自动格式化归档与 Steamtools `.lua` 规则生成。

## ✨ 核心特性

- 🚀 **完全脱离 Steam 客户端**：免客户端挂载，直连 Steam 官方 API 与 CDN 服务器。
- 🔑 **强行捕获解密密钥**：截获并输出 Valve 官方加密限制的 `DecryptionKey`，自动合并输出至 `DecryptionKey.json`。
- 📜 **一键生成 Steamtools Lua**：自动为每个 AppID 生成包含主程序、加密 Depot、无清单 DLC 等完整规则的 `<appid>.lua` 文件。
- 🌐 **Steam Store DLC 自动探测**：自动调用 Steam API 检索已拥有的 DLC，将无清单 DLC 自动补全至 Lua 配置中（支持 Cookies 穿透锁区限制）。
- 📦 **断点续传与批量处理**：支持通过 `task.txt` 批量抓取，`progress.json` 自动记录完成进度，意外中断后无缝跳过已完成项。
- 🛡️ **异常容错与智能重试**：
  - 支持 Steam Guard 动态验证码输入；
  - 遇到连接超时（`A task was canceled`）自动重试 3 次，并在挂起时支持人工决策 `[R]重试 / [S]跳过 / [E]退出`；
  - 会话过期（`RELOGIN`）自动唤起重新登录并无缝继续当前任务；
  - 遇到 `RateLimitExceeded` 速率限制时自动告警并优雅退出，保护账号安全。
- 👥 **多账号配置支持**：自动持久化记录已登录账号列表，支持命令行任意切换。
- ⚡ **零第三方 Python 依赖**：Python 端 100% 基于内置标准库开发，**无需 `pip install` 任何包**，解压即用！

## 📂 项目结构

```text
SteamManifestGrabber/
├── main.py                  # Python 主调度与整理脚本（纯标准库）
├── login.txt                # 已保存的 Steam 账号列表（首行为默认账号）
├── task.txt                 # 批量抓取任务列表（一行一个 AppID，需开启 -b）
├── progress.json            # 批量进度记录（自动生成，支持断点续传）
├── cookies.txt              # （可选）用于访问锁区/敏感 DLC 的 Cookies
├── DecryptionKey.json       # 自动生成的全局解密密钥汇总表
├── DepotDownloader/         # C# 底座二进制目录
│   └── DepotDownloader.exe  # （Linux 下为 DepotDownloader）
└── manifest/                # 抓取成果输出目录
    └── <appid>/
        ├── <depotid>_<manifestid>.manifest
        └── <appid>.lua      # 自动生成的 Steamtools 入库配置文件
```

## 🛠️ 运行环境要求

1. **[.NET 9.0 桌面运行时 (Desktop Runtime)](https://dotnet.microsoft.com/zh-cn/download/dotnet/9.0)**
   * 请前往微软官网下载安装对应系统的 `.NET 桌面运行时 9.0`（Windows x64 / arm64，Linux x64 / arm / arm64）。
2. **[Python 3.8+](https://www.python.org/)**

> ⚠️ **注意**：原版 DepotDownloader 不支持本脚本的密钥截获输出，请使用本仓库配套或 [🔗 Release 页面](https://github.com/ZGQ-inc/DepotDownloader/releases/tag/init) 提供的魔改版 Binary。

## 🚀 快速上手

### 1. 克隆 / 下载项目

```bash
git clone https://github.com/ZGQ-inc/SteamManifestGrabber.git
cd SteamManifestGrabber
```

确保 `DepotDownloader/` 目录下放置了对应平台的魔改版二进制文件：
* **Windows**：`DepotDownloader/DepotDownloader.exe`
* **Linux**：`DepotDownloader/DepotDownloader`（需赋予执行权限：`chmod +x DepotDownloader/DepotDownloader`）

或者直接下载带 DepotDownloader 的打包版本：[DepotDownloader_v1.10.zip](https://assets.zgqinc.gq/images/2026-08/DepotDownloader_v1.10.zip)

### 2. 交互式单游戏抓取

直接运行脚本，首次运行会提示输入 Steam 账号、密码及令牌（密码输入不回显）：

```bash
# Windows
python main.py

# Linux
python3 main.py
```

根据提示输入 AppID 即可自动完成清单下载、密钥解密、DLC 检索与 Lua 生成。

## 💡 进阶使用参数

```text
用法: python main.py [-h] [-a [ACCOUNT]] [-c [COOKIES]] [-b]

参数说明:
  -h, --help            显示帮助信息
  -a, --account ACCOUNT 指定要使用的 Steam 账号名（未指定时使用上次默认账号）
  -b, --batch           启用批处理模式（读取 task.txt 中的 AppID 列表）
  -c, --cookies [PATH]  指定用于访问 Steam API 的 Cookies 文件（默认 cookies.txt）
```

### 1. 批量抓取模式 (`-b / --batch`)

在项目根目录下创建 `task.txt`，填入待抓取的 AppID（每行一个）：
```text
1086940
1091500
1245620
```
运行命令开启全自动流水线抓取：
```bash
python main.py -b
```
> 抓取进度会自动保存在 `progress.json` 中，如遇网络波动中断，再次运行将自动跳过已完成项。

### 2. 切换账号 (`-a / --account`)

```bash
python main.py -a my_alt_account
```

### 3. 使用 Cookies 绕过 DLC 锁区/年龄验证 (`-c / --cookies`)

若部分锁区游戏或包含敏感内容的 DLC 无法通过公开 API 获取，可使用浏览器插件（如 *Get cookies.txt LOCALLY*）导出 Steam 商店的 `cookies.txt` 放入根目录：
```bash
python main.py -b -c cookies.txt
```

## 🎯 技巧：如何极速生成名下全部 AppID 列表？

1. 打开浏览器登录并访问 [SteamDB 已购游戏列表](https://steamdb.info/sales/?displayOnly=OwnedGames)；
2. 按 `F12` 打开开发者工具，在 **Elements / 元素** 面板中复制 `<body>` 标签的整体 HTML，保存为本地文件 `steam.html`；
3. 打开终端执行以下正则表达式提取命令，即可瞬间生成干净的 `task.txt`：
   ```bash
   grep -oP '(?<=<a class="b" href="/app/)\d+' steam.html > task.txt
   ```
4. 运行 `python main.py -b` 即可全自动挂机提取名下全部游戏清单与密钥！

## ⚠️ 注意事项与安全提示

1. **Session 凭证路径硬编码保护**：
   出于安全机制设计，登录成功后生成的 `.session` 凭证是与**脚本当前的绝对运行路径**绑定的。若将整个文件夹移动到其他盘符或目录，会话将失效并提示重新登录。
2. **账号安全警示**：
   登录凭据保存在本地，**严禁在任何公共电脑或不受信任的环境中运行本工具**。
3. **风控冷却机制**：
   若频繁登录或短时间内触发 Steam 速率保护（`RateLimitExceeded`），请**完全停止运行并等待 30 分钟至 1 小时**后再试，切勿频繁强行重试。

## 📜 开源协议与致谢

- 本项目遵循 [MIT License](LICENSE) 协议开源。
- 核心网络底座基于 [SteamRE/SteamKit](https://github.com/SteamRE/SteamKit) 与魔改版 [ZGQ-inc/DepotDownloader](https://github.com/ZGQ-inc/DepotDownloader)。

> ⚠️ **免责声明**：本项目仅用于正版游戏资产备份、数据归档与逆向技术交流，严禁用于任何侵犯版权或违反 Steam 服务协议（SSA）的商业用途。