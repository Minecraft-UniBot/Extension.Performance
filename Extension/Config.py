"""Performance 扩展配置模型。"""

from pydantic import BaseModel, Field


class CommandSource(BaseModel):
    """指令 + 正则数据源。"""

    # 执行的 RCON 指令（不含斜杠）。留空则停用该数据源。
    command: str = Field(default='spark tps', description='RCON 指令（无需斜杠），留空停用该数据源')

    # 从指令输出中解析 TPS 的正则，须含一个捕获组；留空使用内置默认（兼容 spark tps / vanilla tps）。
    tps_pattern: str = Field(default='', description='解析 TPS 的正则（含一个捕获组），留空使用内置默认')

    # 从指令输出中解析 MSPT 的正则；留空表示该源不解析 MSPT。
    mspt_pattern: str = Field(default='', description='解析 MSPT 的正则（含一个捕获组），留空不解析 MSPT')

    @property
    def enabled(self) -> bool:
        """判断数据源是否启用。"""
        return bool(self.command)


class Threshold(BaseModel):
    """阈值告警规则。"""

    # 目标服务器：留空对全部已连接服务器生效，否则为编号/名称
    server: str = Field(default='', description='目标服务器编号/名称，留空监控全部已连接服务器')

    # TPS 过低告警阈值：低于该值触发，置 0 停用
    min_tps: float = Field(default=15.0, ge=0, description='TPS 低于该值触发告警，置 0 停用')

    # MSPT 过高告警阈值：高于该值触发，置 0 停用
    max_mspt: float = Field(default=0.0, ge=0, description='MSPT 高于该值触发告警，置 0 停用')


class PerformanceConfig(BaseModel):
    """
    性能监控扩展的业务配置。

    提供两种取数途径（命令 + 正则 / 占位符服务），支持手动查询权限控制、
    定时监控与阈值告警。配置持久化到 `Config/Extensions/Performance.toml`。
    """

    # ===== 手动查询指令 =====

    # 是否允许普通用户查询，默认 False（仅管理员）
    query_public: bool = Field(default=False, description='是否允许普通用户查询，默认仅管理员可查')

    # ===== 指令 + 正则数据源 =====

    # 指令数据源列表，按顺序依次尝试，首个成功解析到 TPS 即返回。
    command_sources: list[CommandSource] = Field(
        default_factory=lambda: [CommandSource(command='spark tps'), CommandSource(command='tps')],
        description='指令数据源列表，按顺序尝试；已内置 spark tps 与 vanilla tps 默认正则',
    )

    # 单次 RCON 指令执行超时（秒）
    command_timeout: float = Field(default=5.0, ge=0.5, description='单次 RCON 指令执行超时（秒）')

    # ===== 占位符数据源 =====

    # 是否启用占位符数据源（依赖已安装的市场扩展 Extension.Placeholder）
    placeholder_source_enabled: bool = Field(default=False, description='是否启用占位符数据源（需安装占位符 API 扩展）')

    # 取 TPS / MSPT 的占位符，经 PlaceholderService.get() 取值
    placeholder_tps: str = Field(default='%server_tps%', description='取 TPS 的占位符')
    placeholder_mspt: str = Field(default='%server_mspt%', description='取 MSPT 的占位符')

    # ===== 定时监控与阈值告警 =====

    # 是否启用定时监控
    monitor_enabled: bool = Field(default=False, description='是否启用定时监控')

    # 定时监控目标服务器：留空监控全部已连接服务器
    monitor_server: str = Field(default='', description='定时监控的目标服务器编号/名称，留空监控全部')

    # 监控与告警采集间隔（秒）
    monitor_interval: float = Field(default=60.0, ge=5, description='监控采集间隔（秒）')

    # 达到阈值后是否持续告警；关闭时恢复后再次越界才重新告警
    alert_repeat: bool = Field(default=False, description='是否对持续越界重复告警')

    # 阈值规则列表
    thresholds: list[Threshold] = Field(default_factory=lambda: [Threshold()], description='阈值告警规则列表')