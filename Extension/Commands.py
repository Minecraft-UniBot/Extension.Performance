"""Performance 性能查询指令。

提供 TPS / MSPT 查询指令，可按配置开放给普通用户或仅限管理员。
数据采集逻辑由扩展自身的 `helper`（PerformanceHelper）承担，本模块只负责指令解析与结果渲染。
"""

from abc import ABC
from typing import override

from nonebot_plugin_alconna import Match
from nonebot_plugin_uninfo import Uninfo

from Scripts.Extensions import Command
from Scripts.Utils import get_permission

from . import extension


class _PerformanceQuery(Command, ABC):
    """TPS / MSPT 查询的共享基类：提供权限校验与结果渲染，子类声明取值字段。"""

    # 子类声明要展示的字段元数据：(result 键, 显示标签, 是否带单位 ms)
    display_fields: tuple[tuple[str, str, bool], ...] = ()

    @override
    def declare(self) -> None:
        # 可选参数：目标服务器编号/名称，缺省取第一台在线服务器
        self.register_option('server', str, default=None, description='目标服务器编号/名称，缺省自动选择')

    @override
    async def handler(self, session: Uninfo, server: Match[str]):
        if not self._can_query(session):
            return '你没有权限执行此指令。'
        server_flag = server.result if server.available else None
        result = await extension.helper.fetch(server_flag)
        return self._render_text(result)

    def _can_query(self, session) -> bool:
        """判断是否允许本次查询（按配置开放给普通用户或仅管理员）。"""
        config = extension.config.value
        if config.query_public:
            return True
        return get_permission(session)

    def _render_text(self, result: dict) -> str:
        """以文本形式格式化查询结果。"""
        if result['tps'] is None and result['mspt'] is None:
            if result['source'] == 'none' or not result['server']:
                return '没有可用的服务器或无法获取性能数据，请检查服务器是否在线及数据源配置。'
            return f"[{result['server']}] 未能解析到 TPS/MSPT，请检查数据源指令与正则配置。"
        server_name = result['server'] or '未知服务器'
        parts = [f'服务器：{server_name}']
        for key, label, is_ms in self.display_fields:
            value = result[key]
            if value is None:
                continue
            parts.append(f'{label}：{value:.1f}' + ('ms' if is_ms else ''))
        parts.append(f"来源：{result['source']}")
        return '\n'.join(parts)


@extension.register_command
class PerfQuery(_PerformanceQuery):
    """查询服务器 TPS 与 MSPT 性能指标。"""

    name = 'perf'
    description = '查询服务器 TPS / MSPT 性能指标。'
    usage = '/perf [服务器]'
    display_fields = (('tps', 'TPS', False), ('mspt', 'MSPT', True))


@extension.register_command
class TpsQuery(_PerformanceQuery):
    """查询服务器 TPS 性能指标。"""

    name = 'tps'
    description = '查询服务器 TPS 性能指标。'
    usage = '/tps [服务器]'
    display_fields = (('tps', 'TPS', False),)


@extension.register_command
class MsptQuery(_PerformanceQuery):
    """查询服务器 MSPT 性能指标。"""

    name = 'mspt'
    description = '查询服务器 MSPT 性能指标。'
    usage = '/mspt [服务器]'
    display_fields = (('mspt', 'MSPT', True),)
