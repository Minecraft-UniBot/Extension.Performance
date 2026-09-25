"""Performance 性能查询指令。

提供 TPS / MSPT 查询指令，可按配置开放给普通用户或仅限管理员。
数据采集逻辑由扩展自身的 `helper`（PerformanceHelper）承担，本模块只负责指令解析与结果渲染。

多服务器约定与内置指令（`/list`、`/server`）保持一致：
    - 缺省或传 `*`：查询全部已连接服务器，逐行以 `[服务器名]` 前缀展示；
    - 传编号 / 名称：仅查询该服务器；
    - 编号取自 `/server` 展示的服务器列表顺序（从 1 开始）。
"""

from abc import ABC
from typing import override

from nonebot_plugin_alconna import Match
from nonebot_plugin_uninfo import Uninfo

from Scripts.Extensions import Command
from Scripts.Utils import get_permission

from . import extension

# 目标服务器参数取值：显式指定全部服务器
ALL_SERVERS_FLAG = '*'

# 指令对外文本
NO_PERMISSION = '你没有权限执行此指令。'
NO_SERVER = '当前没有已连接的服务器，无法查询性能数据！'
SERVER_NOT_FOUND = '没有找到已连接的 [{server}] 服务器！请检查编号或名称是否输入正确。'
FIELD_LINE = '[{server}] {fields}'
SERVER_FAILED = '[{server}] 数据获取失败，请检查服务器状态与数据源配置。'


class _PerformanceQuery(Command, ABC):
    """TPS / MSPT 查询的共享基类：提供权限校验与结果渲染，子类声明取值字段。"""

    # 子类声明要展示的字段元数据：(result 键, 显示标签, 是否带单位 ms)
    display_fields: tuple[tuple[str, str, bool], ...] = ()

    @override
    def declare(self) -> None:
        # 可选参数：目标服务器编号/名称；缺省或 * 表示查询全部已连接服务器
        self.register_option(
            'server', str, default=None, description='目标服务器编号/名称，* 或缺省表示查询全部服务器'
        )

    @override
    async def handler(self, session: Uninfo, server: Match[str]) -> str | None:
        if not self._can_query(session):
            return NO_PERMISSION
        server_flag = server.result if server.available else None
        results = await extension.helper.fetch_many(server_flag)
        if not results:
            if server_flag and server_flag.strip() != ALL_SERVERS_FLAG:
                return SERVER_NOT_FOUND.format(server=server_flag)
            return NO_SERVER
        return '\n'.join(self._render_fields(result) for result in results)

    def _can_query(self, session: Uninfo) -> bool:
        """判断是否允许本次查询（按配置开放给普通用户或仅管理员）。"""
        config = extension.config.value
        if config.query_public:
            return True
        return get_permission(session)

    def _render_fields(self, result: dict) -> str:
        """渲染单台服务器的一行指标；无有效数据时给出失败提示。"""
        fields = [
            f'{label}：{result[key]:.1f}' + ('ms' if is_ms else '')
            for key, label, is_ms in self.display_fields
            if result.get(key) is not None
        ]
        if not fields:
            return SERVER_FAILED.format(server=result['server'])
        return FIELD_LINE.format(server=result['server'], fields=' '.join(fields))


@extension.register_command
class PerfQuery(_PerformanceQuery):
    """查询服务器 TPS 与 MSPT 性能指标。"""

    name = 'perf'
    description = '查询服务器 TPS / MSPT 性能指标。'
    usage = '/perf [服务器|*]'
    display_fields = (('tps', 'TPS', False), ('mspt', 'MSPT', True))


@extension.register_command
class TpsQuery(_PerformanceQuery):
    """查询服务器 TPS 性能指标。"""

    name = 'tps'
    description = '查询服务器 TPS 性能指标。'
    usage = '/tps [服务器|*]'
    display_fields = (('tps', 'TPS', False),)


@extension.register_command
class MsptQuery(_PerformanceQuery):
    """查询服务器 MSPT 性能指标。"""

    name = 'mspt'
    description = '查询服务器 MSPT 性能指标。'
    usage = '/mspt [服务器|*]'
    display_fields = (('mspt', 'MSPT', True),)
