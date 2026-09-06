"""
Performance 扩展包入口。

查询 Minecraft 服务器 TPS/MSPT 性能指标，支持命令 + 正则与占位符两种数据源、
定时监控与阈值告警。依赖内置 `Servers` 扩展执行 RCON 指令。

布局说明：
    Extension.toml    清单：声明类型与依赖（Servers）
    __init__.py       入口：定义扩展实例（子类化 Extension，生命周期启停监控）
    Config.py         配置模型（pydantic BaseModel）
    Commands.py       指令定义（/perf 查询）
    Services.py       内部采集辅助（非注册能力，供扩展本体复用）
"""

from typing import override

from Scripts.Extensions import Extension

from .Config import PerformanceConfig
from .Services import PerformanceHelper


class PerformanceExtension(Extension):
    """性能监控扩展：重载生命周期以启停定时监控与告警。"""

    def __init__(self) -> None:
        super().__init__(config_model=PerformanceConfig)
        self.helper = PerformanceHelper(self)

    @override
    async def on_enable(self) -> None:
        """扩展启用时启动定时监控。"""
        await self.helper.start()

    @override
    async def on_disable(self) -> None:
        """扩展停用时停止定时监控并清理告警状态。"""
        await self.helper.stop()


# 唯一扩展实例。id/name/version 等元数据以 Extension.toml 为准，无需在此声明。
extension = PerformanceExtension()

# 能力模块在扩展实例创建后导入，经相对导入获取同一实例。
# 注意导入顺序：先 Config（无依赖），再 Services / Commands（依赖 extension）。
from . import Commands  # noqa: E402,F401
