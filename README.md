<p align="center">
  <img src=".github/images/icon.svg" alt="Performance" width="140" />
</p>

<h1 align="center">性能监控 · Performance</h1>

<p align="center">
  查询 Minecraft 服务器 <strong>TPS / MSPT</strong>，支持多数据源、定时监控与阈值告警
</p>

<p align="center">
  <code>📈 TPS</code>
  <code>⏱ MSPT</code>
  <code>🔌 占位符</code>
  <code>⚙️ 阈值告警</code>
  <code>📦 市场就绪</code>
</p>

---

集**指令（command）与配置**于一身，为 UniBot 提供服务器性能监测能力。

- **类型**：`command`
- **依赖**：内置 `Servers` 扩展（执行 RCON 指令）；占位符数据源可选依赖市场 `Placeholder` 扩展
- **版本对应**：兼容 UniBot `*`

## ✨ 功能一览

| 能力 | 说明 |
|------|------|
| 📈 **TPS 查询** | 查询服务器当前 TPS |
| ⏱ **MSPT 查询** | 查询服务器当前 MSPT |
| 🖥 **多服务器** | 缺省或传 `*` 一次查询全部已连接服务器，逐台分区展示 |
| 🧪 **多数据源** | 支持「RCON 指令 + 正则」与「占位符服务」两种取数方式 |
| 🔁 **定时监控** | 按固定间隔轮询服务器性能 |
| 🔔 **阈值告警** | TPS 过低 / MSPT 过高时向机器人的消息群发送告警 |
| 🔐 **权限可配** | 默认仅管理员可查，可放开给普通用户 |

---

## 📦 安装

支持两种安装方式：

**通过 UniBot 插件市场安装**：

1. 在 WebUI 的「插件市场」中搜索 `Performance`。
2. 选择最新版本并点击安装，之后在「扩展管理」中启用。

**手动安装**：

将扩展目录放入 `Extensions/Performance/`，然后在 `Config/Extensions.toml` 中启用：

```toml
[Performance]
enabled = true
```

> 本扩展依赖内置 `Servers` 扩展（默认启用），执行 RCON 指令取数。若启用占位符数据源，
> 还需另外安装市场扩展 `Placeholder`（占位符 API）。

## 🎮 指令

指令前缀继承机器人全局 `command_start`（默认 `#`），以下以 `#` 为例。

### `#perf [服务器|*]` / `#tps [服务器|*]` / `#mspt [服务器|*]`

查询服务器性能指标。行为与内置 `/list`、`/server` 一致，支持多服务器：

- `#perf`：同时查询 TPS 与 MSPT
- `#tps`：仅查询 TPS
- `#mspt`：仅查询 MSPT

`[服务器]` 可填**编号**或**名称**，编号与 `/server` 展示的服务器列表顺序一致（从 1 开始）：

- 缺省或传 `*`：查询**全部**已连接服务器，逐行以 `[服务器名]` 前缀展示；
- 传编号 / 名称：仅查询该服务器；不存在时提示「没有找到已连接的服务器」。

```
#perf            # 查询全部服务器
#mspt *          # 查询全部服务器（显式）
#tps 1           # 查询第 1 台服务器
#mspt 生存服      # 按名称查询
```

输出示例（每台服务器一行，`/perf` 并列展示多项指标）：

```
[生存服] TPS：20.0 MSPT：12.3ms
[创造服] TPS：19.8 MSPT：18.6ms
```

> 权限默认仅管理员；配置 `query_public = true` 后可对所有用户开放。

## ⚙️ 配置

配置可由 WebUI 扩展管理面板修改，或直接编辑 `Config/Extensions/Performance.toml`。

### 查询权限

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `query_public` | `false` | 是否允许普通用户查询（默认仅管理员） |

### 指令 + 正则数据源

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `command_sources` | `spark tps`、`tps` | RCON 指令列表，按顺序尝试；每项可配 `command` / `tps_pattern` / `mspt_pattern` |
| `command_timeout` | `5.0` | 单次 RCON 指令执行超时（秒） |

每个数据源元素包含：

| 字段 | 说明 |
|------|------|
| `command` | 执行的 RCON 指令（不含斜杠），留空停用该数据源 |
| `tps_pattern` | 解析 TPS 的正则（含一个捕获组），留空用内置默认 |
| `mspt_pattern` | 解析 MSPT 的正则（含一个捕获组），留空不解析 MSPT |

内置默认正则兼容 `spark tps`（`TPS from last 5s: 20.0 | MSPT from last 5s: 49.72ms`）
与 vanilla `/tps`（`TPS: 20.0` / `MSPT: 50.0ms`）。服务端未装 spark 时，默认还会尝试 `tps`。

> 若你的服务端输出不同（如中文化或自定义插件），可在 `tps_pattern` / `mspt_pattern`
> 填写自定义正则覆盖默认解析，例如 `TPS 值[:：]\s*(\d+\.?\d*)`。

### 占位符数据源

需另装市场扩展 `Placeholder`（占位符 API），本扩展经其 `PlaceholderService.get()` 取值：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `placeholder_source_enabled` | `false` | 是否启用占位符数据源 |
| `placeholder_tps` | `%server_tps%` | 取 TPS 的占位符 |
| `placeholder_mspt` | `%server_mspt%` | 取 MSPT 的占位符 |

> 占位符仅在指令数据源取不到 TPS 时作为回退尝试。

### 定时监控与告警

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `monitor_enabled` | `false` | 是否启用定时监控 |
| `monitor_server` | `''` | 监控目标服务器（编号/名称），留空监控全部 |
| `monitor_interval` | `60.0` | 监控采集间隔（秒，≥5） |
| `alert_repeat` | `false` | 持续越界是否重复告警；关闭时恢复后再越界才重新告警 |

> 告警直接发送到机器人的**全局消息群**（`Config.toml` 的 `message_groups`），无需在本扩展中额外配置发送目标。

每个阈值规则元素包含：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `server` | `''` | 作用的目标服务器，留空对全部生效 |
| `min_tps` | `15.0` | TPS 低于该值告警，置 `0` 停用 |
| `max_mspt` | `0.0` | MSPT 高于该值告警，置 `0` 停用 |

> 告警需同时满足：`monitor_enabled` 与至少一条阈值规则；发送目标为机器人的消息群。
> 定时监控复用机器人的内置 **TaskService**（定时任务服务）注册周期任务，随扩展生命周期启停。

---

> 采集、监控与告警逻辑收敛于扩展自身内部的 `helper`（见 `Services.py`），随扩展实例的
> 生命周期启停，**不对外注册任何服务能力**，仅供扩展本体内部使用。

## 📁 目录结构

```
Extensions/Performance/
├── Extension.toml      # 清单：声明类型、依赖与版本
├── __init__.py         # 入口：创建扩展实例，生命周期内启停内部监控
├── Config.py           # 配置模型（PerformanceConfig）
├── Commands.py         # 指令定义（/perf、/tps、/mspt）
└── Services.py         # 内部采集辅助（PerformanceHelper，不注册能力）
```

## 🛠 故障排查

| 现象 | 可能原因 | 处理 |
|------|---------|------|
| 查询提示「无法获取性能数据」 | 服务器离线或未装 spark / 无 /tps | 确认服务端已连接且支持 `spark tps` 或 `tps` |
| 解析不到 TPS/MSPT | 服务端输出格式与默认正则不符 | 在数据源配置中填写自定义 `tps_pattern` / `mspt_pattern` |
| 占位符数据源不生效 | 未安装 `Placeholder` 扩展，或未开启开关 | 安装占位符 API 扩展并设 `placeholder_source_enabled = true` |
| 告警不发送 | 未满足告警前置条件，或未配置消息群 | 确认 `monitor_enabled` 与阈值规则已配置，且 `Config.toml` 的 `message_groups` 非空 |
| 指令无权限提示 | 默认仅管理员可查 | 设 `query_public = true` 或让管理员执行 |

## 📤 发布到 UniBot 插件市场

遵循 PlaceholderApi 的市场分发流程，编辑 `Extension.toml` 的 `id`/`name`/`version` 后打包发布：

1. **打包**：将扩展目录压缩为 zip，**确保 zip 根目录包含 `Extension.toml`**（zip 根即扩展目录，不要多套一层文件夹）。
2. **发布**：上传 zip 到 GitHub Release。
3. **登记**：在扩展注册表（JSON 索引文件）中登记条目，包含元信息与 Release 资产地址（含 SHA-256 校验和），用户即可在 WebUI「插件市场」搜索并安装。

> 安装时系统会校验 zip 根目录与清单中的 `id` 一致，并拒绝绝对路径、`../` 路径与符号链接，因此打包务必以扩展目录为根。
