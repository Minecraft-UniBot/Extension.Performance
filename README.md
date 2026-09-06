<p align="center">
  <img src=".github/images/icon.svg" alt="Example" width="140" />
</p>

<h1 align="center">示例扩展 · Example</h1>

<p align="center">
  一个演示 <strong>UniBot 扩展开发</strong> 与 <strong>市场发布流程</strong> 的模板扩展
</p>

<p align="center">
  <code>🧩 指令</code>
  <code>🔌 服务</code>
  <code>⚙️ 配置</code>
  <code>📦 市场就绪</code>
</p>

---

集**指令（command）、服务（api）与配置**三类能力于一身，可直接作为新扩展的起点。

- **类型**：`api` + `command`
- **依赖**：无（仅使用框架核心能力）
- **版本对应**：兼容 UniBot `*`

> 💡 本模板按标准多文件扩展布局组织，字段与清单均符合插件市场校验要求，可直接打包上传。

## ✨ 功能一览

| 能力 | 说明 |
|------|------|
| 🎉 **问候** | 按配置模板生成问候语 |
| 🔁 **重复文本** | 将文本重复输出多行，受配置上限约束 |
| 🔌 **示例服务** | 提供 `ExampleService`，供其它扩展复用 |

---

## 📦 安装

支持两种安装方式：

**通过 UniBot 插件市场安装**：

1. 在 WebUI 的「插件市场」中搜索 `Example`。
2. 选择最新版本并点击安装，之后在「扩展管理」中启用。

**手动安装**：

将扩展目录放入 `Extensions/Example/`，然后在 `Config/Extensions.toml` 中启用：

```toml
[Example]
enabled = true
```

> 卸载或禁用后，对应指令与 `ExampleService` 能力将不可用。

## 🎮 指令

指令前缀继承机器人全局 `command_start`（默认 `#`），以下以 `#` 为例。

### `#example greet [目标]`

按配置模板向目标问好，缺省目标时使用当前使用者。

```
#example greet
#example greet 小明
```

### `#example repeat <文本> [次数]`

将文本重复输出多行。`<文本>` 支持多词（贪婪合并），`[次数]` 缺省用配置默认值且受上限约束。

```
#example repeat 打卡，坚持！
#example repeat hello world 2
```

> 缺省参数时命令会返回友好提示（如「请提供要重复的文本。」），不会静默无响应。

## ⚙️ 配置

配置可由 WebUI 扩展管理面板修改，或直接编辑 `Config/Extensions/Example.toml`：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `greeting` | `你好，{name}！` | 问候语模板，`{name}` 会被使用者名替换 |
| `max_repeat` | `3` | 单次重复次数的上限（1–10） |
| `debug` | `false` | 是否输出调试日志 |

---

## 🧩 服务能力

其它扩展可通过 `extension.api.get(ExampleService)` 复用示例能力（服务注册名 `example`）：

```python
from Extensions.Example.Services import ExampleService

service = extension.api.get(ExampleService)
if service is not None:
    message = service.compose_greeting('小明')
```

### 公开方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `compose_greeting` | `compose_greeting(name: str) -> str` | 按配置模板生成问候语 |
| `repeat_text` | `repeat_text(text: str, count: int \| None = None) -> list[str]` | 将文本重复多行，受 `max_repeat` 约束 |

## 📁 目录结构

```
Extensions/Example/
├── Extension.toml      # 清单：声明类型、依赖与版本
├── __init__.py         # 入口：创建扩展实例并登记能力
├── Config.py           # 配置模型（ExampleConfig）
├── Commands.py         # 指令定义（greet / repeat）
└── Services.py         # 服务实现（ExampleService）
```

## 🛠 故障排查

| 现象 | 可能原因 | 处理 |
|------|---------|------|
| 指令提示「示例服务不可用」 | 扩展未被正确加载或服务登记失败 | 确认 `Config/Extensions.toml` 已启用，查看日志 |
| 指令无响应 | 缺参时未兜底返回提示 | 检查 handler 中是否正确判断 `Match.available` 与 `result` |
| 配置修改不生效 | 修改后未重启 | 修改启停/配置后需重启机器人 |

## 📤 发布到 UniBot 插件市场

遵循 PlaceholderApi 的市场分发流程，编辑 `Extension.toml` 的 `id`/`name`/`version` 后打包发布：

1. **打包**：将扩展目录压缩为 zip，**确保 zip 根目录包含 `Extension.toml`**（zip 根即扩展目录，不要多套一层文件夹）。
2. **发布**：上传 zip 到 GitHub Release。
3. **登记**：在扩展注册表（JSON 索引文件）中登记条目，包含元信息与 Release 资产地址（含 SHA-256 校验和），用户即可在 WebUI「插件市场」搜索并安装。

> 安装时系统会校验 zip 根目录与清单中的 `id` 一致，并拒绝绝对路径、`../` 路径与符号链接，因此打包务必以扩展目录为根。

### 开发新扩展时

- 复制本目录，重命名 `id` 与各类名（`Example` → 你的扩展名），替换业务逻辑。
- `id` 仅允许 `A-Za-z0-9_`；指令/参数名小写字母/数字/下划线。
- 若使用第三方库，在 `Extension.toml` 的 `[dependencies].python` 声明，框架会自动同步依赖。
- 若依赖其它扩展的能力，在 `[dependencies].extensions` 声明其 `id`。