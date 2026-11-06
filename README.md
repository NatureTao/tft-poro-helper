# TFT-Poro-Helper

**英雄联盟《云顶之弈》(TFT) 自动化辅助工具 —— 截图识别驱动，图形界面开箱即用。**

<p>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/PySide6-6.11-41CD52?logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Engine-YOLO%20%2B%20EasyOCR-FF6F00" alt="YOLO + EasyOCR">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
</p>

TFT-Poro-Helper 通过**屏幕截图 + YOLO 目标检测 + OCR 文字识别**理解游戏局面，自动完成排队、买牌、刷新商店、买经验、上装备等操作。整个识别与决策流程不读写游戏内存、不注入进程，只依赖画面与官方提供的本地数据接口。

> [!WARNING]
> 自动化脚本可能违反游戏服务条款，存在被处罚的风险。请在使用前阅读文末的[免责声明](#免责声明)。

---

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [界面与使用](#界面与使用)
- [配置说明](#配置说明)
- [阵容文件格式](#阵容文件格式)
- [工作原理](#工作原理)
- [目录结构](#目录结构)
- [常见问题](#常见问题)
- [已知限制](#已知限制)
- [免责声明](#免责声明)
- [许可证](#许可证)

---

## 功能特性

| 模块 | 说明 |
| --- | --- |
| **自动排队** | 通过英雄联盟客户端 LCU 本地接口创建房间、发起匹配、自动接受对局，支持匹配（1090）与排位（1100）两种模式 |
| **棋盘识别** | YOLO 模型检测棋盘/备战区/商店中的英雄、装备、羁绊图标，OCR 识别金币、等级、血量、回合数 |
| **自动运营** | 按阵容评分自动买牌、卖牌、刷新商店、购买经验、合成与分配装备 |
| **阵容评分** | `services/tft_scorer.py` 根据当前手牌、装备、羁绊、强化符文与商店状态，对内置阵容实时打分并选择最优路线 |
| **阵容库** | 内置 25 套当前赛季阵容配置，支持自定义新增 |
| **图形界面** | 基于 PySide6 + qfluentwidgets 的 Fluent Design 界面，含首页状态面板、阵容管理、参数设置 |
| **桌面覆盖层** | 全屏透明、鼠标穿透的 Overlay，实时显示决策日志、状态摘要与棋盘英雄标签 |
| **实时数据** | 通过 Live Client Data API（`:2999`）读取等级与存活状态，通过 LCU API 读取召唤师信息、段位与货币 |
| **多语言** | 界面支持简体中文 / 繁体中文 / English（`ui/i18n.py`） |
| **游戏数据更新** | 从 META_TFT 拉取最新英雄、装备、羁绊数据，写入 `config/game_data_*.json` |

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11（64 位）——依赖 `pywin32`、`PyDirectInput`，**不支持** macOS / Linux |
| Python | **3.12**（开发验证版本 3.12.10） |
| 分辨率 | 游戏画面按 **1920×1080** 为基准设计；其它分辨率会按比例缩放坐标，但识别精度以 1080p 最佳 |
| 显示模式 | 游戏需使用**窗口化 / 无边框窗口**模式（脚本通过抓取窗口画面工作，独占全屏无法截图） |
| 游戏 | 英雄联盟客户端 + 云顶之弈对局；游戏窗口标题默认 `League of Legends (TM) Client`，可在设置中修改 |
| 显卡 | 可选。NVIDIA 显卡可开启 GPU 加速（`引擎设置 → 调用显卡`） |
| 权限 | 建议以**管理员身份**运行，否则模拟点击可能被游戏窗口忽略 |

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/NatureTao/tft-poro-helper.git
cd tft-poro-helper
```

> **注意**：仓库的默认分支目前仍是 `main`，而 `main` 只保留了初始文件、**不含源码**。
> 唯一可用的开发线是 `dev`，克隆后请显式切换：
>
> ```bash
> git checkout dev
> ```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt
```

依赖包含 `torch` + `torchvision`、`opencv-python`、`easyocr`、`PySide6`、`PySide6-Fluent-Widgets`、`pywin32`、`PyDirectInput` 等，首次安装体积较大（CPU 版通常 2 GB 以上，带 CUDA 则更大），请预留磁盘空间与时间。

> 如需 GPU 推理，请按 [PyTorch 官方指引](https://pytorch.org/get-started/locally/) 安装对应 CUDA 版本的 `torch`。

### 3. 确认模型文件

模型文件位于 `models/` 目录，运行 `main.py` 前必须存在：

| 文件 | 大小 | 用途 | 是否已随仓库分发 |
| --- | --- | --- | --- |
| `models/tft_yolo_v5.onnx` | 9.8 MB | 棋盘 / 商店目标检测（YOLOv5 导出的 ONNX） | ✅ 是 |
| `models/craft_mlt_25k.pth` | 79 MB | EasyOCR 文本检测模型（CRAFT） | ✅ 是 |
| `models/zh_sim_g2.pth` | 21 MB | EasyOCR 简体中文识别模型 | ✅ 是 |

以上三件套即 `ocr.py` 中 `easyocr.Reader(['ch_sim'])` 所需的全部权重，克隆后无需额外下载。

若 `models/` 下缺少文件，可自行从以下来源获取并放置到同名路径：

- `craft_mlt_25k.pth` / `zh_sim_g2.pth`：[EasyOCR Releases](https://github.com/JaidedAI/EasyOCR/releases)
- `tft_yolo_v5.onnx`：随仓库分发；若缺失请联系作者

> `models/chinese.pth`（216 MB，繁体中文）与 `models/english_g2.pth`（14 MB，英文）是 EasyOCR 的可选模型，本项目**不加载**，无需准备。

### 4. 启动

```bash
python main.py
```

程序启动后会注册字体、打开主窗口，并在后台线程预加载 YOLO、OCR 与游戏数据；三项全部就绪后「开始」按钮才可用。首次启动因需加载模型会稍慢。

---

## 界面与使用

主窗口标题为 `TFT-Poro-Helper`，左侧导航包含：

| 页面 | 内容 |
| --- | --- |
| **首页** | 启动 / 停止控制、运行状态、召唤师信息卡片（头像、段位、货币）、快捷设置、实时日志控制台 |
| **阵容** | 阵容库浏览与选择，查看每套阵容的英雄、星级、装备与推荐/规避强化符文 |
| **更新** | 游戏数据更新入口（当前为占位页） |
| **设置** | 挂机、运营、引擎、系统四组参数的图形化配置，写入 `config/setting.json` |
| **使用说明** | 占位页 |
| **交流群** | 占位页 |

**典型使用流程：**

1. 打开英雄联盟客户端并登录，进入云顶之弈大厅。
2. 启动 `main.py`，在「阵容」页选择要使用的阵容。
3. 在「设置」页确认游戏模式（匹配 1090 / 排位 1100）、对局次数、投降与关机策略。
4. 回到「首页」点击开始，脚本自动创建房间 → 匹配 → 接受对局 → 对局内自动运营。
5. 运行时可通过全屏 Overlay 观察决策过程；随时可停止。

---

## 配置说明

配置文件为 `config/setting.json`，可手工编辑（程序关闭时修改），也可通过「设置」页面调整。分组说明：

| 分组 | 键 | 说明 |
| --- | --- | --- |
| **挂机设置** | `游戏模式` | `1090` 匹配 / `1100` 排位 |
| | `对局次数` | 完成多少局后停止 |
| | `主动投降` / `投降时间` | 是否到点投降，及投降触发时间（秒） |
| | `自动关机` | 达到对局次数后是否自动关机 |
| **游戏运营** | `选择阵容` | 使用的阵容文件名（留空则自动选） |
| | `最小金币` / `最大金币` | 保留金币区间，超出上限才刷新商店 |
| | `购买经验刷新商店` | 买经验后是否顺带刷新商店 |
| | `不买经验等级` | 到达这些等级时不再购买经验（如 `[9]`） |
| | `生命阈值` | 血量低于该值时转为激进运营 |
| | `装备阈值` / `随机上装备` | 装备数量达到阈值后随机分配 |
| | `生命值低随机上装备` | 低血量时是否强制上装备 |
| **引擎设置** | `模型` | `fast` / `slow` 检测精度模式 |
| | `调用显卡` | 是否使用 GPU 推理（NVIDIA） |
| | `多进程` / `多进程数` | 是否启用多进程图像检测及进程数 |
| **系统设置** | `游戏窗口` | 游戏窗口标题，用于定位窗口 |
| | `标记颜色` / `标记字体` | Overlay 标记的颜色（RGBA）与字体 |

其它配置文件：

- `config/game_data_zh_CN.json`、`game_data_zh_TW.json`、`game_data_en_US.json` —— 三语游戏数据（英雄、装备、羁绊），由「更新」功能或 `services/game_data_update.py` 刷新。
- `config/resource.json` —— 资源与图标索引。

---

## 阵容文件格式

每套阵容是 `squads/` 下的一个 JSON 文件，文件名即阵容名（如 `【4重薇古丝95】4重装战士3牧羊人2暗星.json`）：

```json
{
  "HERO": {
    "小木灵": { "seat": 1, "items": [], "star": 2 },
    "努努和威朗普": { "seat": 5, "items": ["救赎", "狂徒铠甲", "圣盾使的誓约"], "star": 2 }
  },
  "AUGMENTS": ["低调炫耀", "镀金钢铁", "双排"],
  "AVOID_AUGMENTS": ["潘朵拉的备战席", "潘朵拉的席位"]
}
```

| 字段 | 含义 |
| --- | --- |
| `HERO` | 英雄名 → `seat`（1–6 为棋盘位，21/23/25/27… 为备战区位）、`items`（推荐装备）、`star`（目标星级） |
| `AUGMENTS` | 推荐强化符文 |
| `AVOID_AUGMENTS` | 应规避的强化符文 |

新增阵容只需按上述格式放入 `squads/`，重启程序后即可在「阵容」页看到。
部分阵容数据可由 `services/tft_lineup_service.py` 从腾讯 TFT 阵容库拉取并转换为本格式。

---

## 工作原理

```
        ┌──────────────┐
        │ 游戏窗口画面 │
        └──────┬───────┘
               │ 截图 (PIL.ImageGrab)
        ┌──────▼───────┐        ┌──────────────────┐
        │ 图像预处理   │──────▶ │ YOLO (ONNX) 检测 │──┐
        │ 灰度/二值化  │        └──────────────────┘  │ 英雄/装备/图标
        └──────┬───────┘        ┌──────────────────┐  │
               └──────────────▶ │ EasyOCR 文字识别 │──┤ 金币/等级/血量
                                └──────────────────┘  │
        ┌──────────────────┐                        │
        │ Live Client API  │────────────────────────┤ 等级/存活
        │ LCU API          │────────────────────────┤ 玩家/段位/货币
        └──────────────────┘                        ▼
                                          ┌──────────────────┐
                                          │ 阵容评分与决策   │
                                          │ services/…      │
                                          └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │ 模拟输入         │
                                          │ PyDirectInput    │
                                          └──────────────────┘
```

**进程结构**：主进程承载 Qt 界面；点击「开始」后由 `bot_controller.py` 派生两个子进程——`game_loop.py`（排队与对局循环，内部持有 `game.py` 的 `Game` 实例）与 `overlay.py`（透明覆盖层），两者通过 `multiprocessing.Queue` 与主进程通信。

**核心模块职责：**

| 文件 | 职责 |
| --- | --- |
| `main.py` | 统一入口：注册字体、启动窗口、后台预加载 YOLO/OCR/游戏数据、初始化控制器 |
| `bot_controller.py` | 机器人生命周期（启动/暂停/停止）与子进程管理 |
| `game_loop.py` | 大循环：匹配 → 建局 → 进入对局 → 回合处理 |
| `game.py` | 回合内任务调度（选秀、野怪、商店、装备、升级、站位） |
| `game_functions.py` | 对局数据检索（回合、存活、拾取、投降） |
| `arena.py` / `arena_functions.py` | 棋盘与备战区状态建模、OCR 数据采集 |
| `screen_coords.py` / `vec2.py` / `vec4.py` | 以 1920×1080 为基准的静态坐标与按窗口尺寸缩放 |
| `ocr.py` | EasyOCR 封装与图像预处理（灰度、Otsu 二值化） |
| `mk_functions.py` | 向游戏发送点击/拖拽等模拟输入 |
| `auto_queue.py` | 通过 LCU 接口创建房间、匹配、自动接受 |
| `champion.py` / `comps.py` | 英雄实体与阵容配置加载 |
| `game_assets.py` | 从 `config/game_data_zh_CN.json` 加载英雄与装备数据 |

---

## 目录结构

```
tft-poro-helper/
├─ main.py                 # 程序入口（字体、窗口、预加载、控制器）
├─ bot_controller.py       # 机器人进程管理
├─ game_loop.py            # 排队与对局主循环
├─ game.py                 # 回合内任务调度
├─ game_functions.py       # 对局数据检索
├─ arena.py / arena_functions.py   # 棋盘与备战区状态
├─ champion.py / comps.py  # 英雄实体、阵容配置
├─ game_assets.py          # 英雄/装备数据加载
├─ ocr.py                  # EasyOCR 封装
├─ mk_functions.py         # 模拟鼠标/键盘输入
├─ auto_queue.py           # LCU 排队与自动接受
├─ overlay.py              # 全屏透明覆盖层
├─ screen_coords.py        # 静态屏幕坐标
├─ vec2.py / vec4.py       # 坐标与缩放
├─ settings.py             # 配置读取
├─ requirements.txt        # 依赖清单
├─ config/                 # setting.json、三语游戏数据、resource.json
├─ models/                 # YOLO 与 EasyOCR 权重
├─ squads/                 # 25 套阵容 JSON
├─ services/               # 数据与评分服务（LCU、阵容、评分、游戏数据更新）
├─ ui/                     # PySide6 界面（首页、阵容、设置、组件、i18n、图标）
├─ utils/                  # 日志工具
├─ fonts/                  # MiSans 字体（不入库，可选）
├─ logs/                   # 运行日志（不入库）
└─ test/                   # 本地测试脚本
```

---

## 常见问题

**Q：点击「开始」没有反应，或 Overlay 不显示？**
确认三个预加载项全部就绪（观察日志区的「[预加载] 全部就绪」），并确认游戏窗口标题与 `设置 → 游戏窗口` 一致。

**Q：模拟点击无效？**
以管理员身份运行；确认游戏为窗口化/无边框模式且处于前台。部分输入法或录屏软件也会拦截模拟点击。

**Q：OCR 提示找不到模型？**
`ocr.py` 中 `model_storage_directory` 指向 `models` 目录。当前该值为绝对路径，**仓库换到别的位置后需要同步修改**为你的 `models/` 路径。

**Q：识别结果不准/串字？**
优先使用 1920×1080 窗口；调高 `引擎设置 → 模型` 为 `slow`；确保 Overlay 的标记字体与颜色不会遮挡识别区域。

**Q：能否在 macOS / Linux 上运行？**
不能。项目依赖 `pywin32`（窗口枚举）、`PyDirectInput`（底层输入模拟）与 Windows 原生截图，仅支持 Windows。

**Q：会不会读写游戏内存或注入 DLL？**
不会。全部信息来自屏幕像素、Live Client Data API 与 LCU 本地接口。

---

## 已知限制

- 「更新」「使用说明」「交流群」三个页面目前是**空白占位**，对应功能尚未实现。
- 游戏数据与阵容以当前赛季（`settings.py` 中 `TFT_SEASON = "s17"`）为准，赛季更新后需重新拉取数据、维护阵容库。
- 屏幕坐标以 1920×1080 标定，其它分辨率依赖 `Vec4` 的线性缩放，边缘位置可能有偏差。
- 多进程检测与 GPU 推理默认关闭，开启后需自行评估稳定性与显存占用。

---

## 免责声明

本项目仅供**学习与个人研究**使用，用于交流计算机视觉（YOLO/OCR）、桌面自动化与 PySide6 界面开发技术。

- 使用本工具可能违反《英雄联盟》/《云顶之弈》的服务条款，**存在账号被警告、封禁的风险**，风险由使用者自行承担。
- 作者不对使用本工具造成的任何账号处罚、数据丢失或其它损失负责。
- 请勿将本项目用于商业代练、账号交易或任何破坏游戏公平性的盈利行为。
- 若你代表版权方并认为本项目存在问题，请联系作者，我们将配合处理。

**下载或运行本项目即表示你已阅读、理解并同意上述条款。**

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源，Copyright © 2026 PeachDreamland。

---

## 致谢

- [EasyOCR](https://github.com/JaidedAI/EasyOCR) —— 文本检测与识别
- [Ultralytics](https://github.com/ultralytics/ultralytics) —— YOLO 目标检测
- [PySide6](https://www.qt.io/qt-for-python) / [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) —— 图形界面
- 最早的 TFT-OCR-BOT 开源项目及其社区 —— 本项目在棋盘坐标与自动化流程设计上受其启发