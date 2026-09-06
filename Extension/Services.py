"""Performance 内部性能采集辅助。

本模块不注册任何能力，仅供扩展本体内部复用。TPS/MSPT 采集、定时监控与阈值告警
逻辑收敛于此，由扩展实例在生命周期钩子中调用。
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from typing import TYPE_CHECKING, Any

from Scripts.Extensions.Builtin.Services.Servers import ServerService
from Scripts.Logging import logger
from Scripts.Utils import send_message_to_groups, strip_minecraft_color

if TYPE_CHECKING:
    from Scripts.Extensions import Extension

# 内置默认正则：兼容 spark tps 与 vanilla /tps 的常见输出格式
#   spark：   "TPS from last 5s: 20.0  |  MSPT from last 5s: 49.72ms"
#   vanilla： "TPS: 20.0" 或 "TPS from last 1m: 20.0" 等
_DEFAULT_TPS_PATTERN = re.compile(
    r'TPS(?: from last \d+(?:\.\d+)?[smhd])?\s*[:：]\s*(\d+(?:\.\d+)?)',
    re.IGNORECASE,
)
_DEFAULT_MSPT_PATTERN = re.compile(
    r'MSPT(?: from last \d+(?:\.\d+)?[smhd])?\s*[:：]\s*(\d+(?:\.\d+)?)',
    re.IGNORECASE,
)


class PerformanceHelper:
    """TPS/MSPT 采集、定时监控与阈值告警的内部辅助类。"""

    def __init__(self, extension: Extension) -> None:
        self._extension = extension
        self._monitor_task: asyncio.Task | None = None
        # 各服务器告警冷却截止时间（time.monotonic 相对时间）：{server_name: cooldown_end}
        self._cooldowns: dict[str, float] = {}

    # ===== 对外能力 =====

    async def start(self) -> None:
        """按配置启动定时监控任务。"""
        if self._config.monitor_enabled and self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop(), name='performance-monitor')
            logger.success('Performance monitor started.')

    async def stop(self) -> None:
        """停止定时监控任务并清空告警冷却状态。"""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
            self._cooldowns.clear()
            logger.info('Performance monitor stopped.')

    async def fetch(self, server_flag: str | int | None = None) -> dict[str, Any]:
        """
        获取指定服务器的 TPS / MSPT。

        依次尝试指令与占位符数据源，首个成功取得 TPS 即返回。
        返回 `{'server': 名称, 'tps': float|None, 'mspt': float|None, 'source': 来源}`。
        """
        server_service = self._server_service()
        if server_service is None or not server_service.check_online():
            return self._empty_result()
        server = self._resolve_server(server_service, server_flag)
        if server is None:
            return self._empty_result()
        server_name = server.self_id

        result = await self._fetch_from_command(server)
        if result['tps'] is None and self._config.placeholder_source_enabled:
            placeholder_result = await self._fetch_from_placeholder(server)
            placeholder_result['source'] = 'placeholder' if placeholder_result['tps'] is not None else 'none'
            result = placeholder_result
        result['server'] = server_name
        return result

    async def monitor_round(self) -> None:
        """执行一轮监控采集，并按阈值规则向消息群发送告警。"""
        config = self._config
        if not (config.monitor_enabled and config.thresholds):
            return
        server_service = self._server_service()
        if server_service is None or not server_service.check_online():
            return
        targets = self._collect_target_servers(server_service, config.monitor_server)
        for server in targets:
            server_name = server.self_id
            result = await self.fetch(server_name)
            if result['tps'] is None and result['mspt'] is None:
                continue
            rules = [rule for rule in config.thresholds if self._rule_matches(rule, server_name)]
            for message in self._build_violations(server_name, result, rules):
                await self._send_alert(message)

    # ===== 采集实现 =====

    @property
    def _config(self):
        """读取当前扩展配置。"""
        return self._extension.config.value

    def _server_service(self):
        """获取内置服务器服务，缺失返回 None。"""
        return self._extension.api.get(ServerService)

    def _placeholder_service(self):
        """按注册名获取占位符 API 服务（未安装时返回 None）。"""
        return self._extension.api.get('placeholder')

    async def _fetch_from_command(self, server) -> dict[str, Any]:
        """通过 RCON 指令 + 正则采集，多个指令源依次尝试。"""
        config = self._config
        for source in config.command_sources:
            if not source.enabled:
                continue
            command = source.command.strip().lstrip('/')
            if not command:
                continue
            try:
                output = await asyncio.wait_for(
                    server.send_rcon_command(command=command),
                    timeout=config.command_timeout,
                )
            except Exception as error:
                logger.warning(f'Performance command [{command}] on [{server.self_id}] failed: {error}')
                continue
            output = strip_minecraft_color(output) if output else ''
            if not output:
                continue
            tps = self._parse_value(output, source.tps_pattern, _DEFAULT_TPS_PATTERN)
            mspt = self._parse_value(output, source.mspt_pattern, _DEFAULT_MSPT_PATTERN)
            if tps is not None:
                return {'tps': tps, 'mspt': mspt, 'source': f'command:{command}'}
        return {'tps': None, 'mspt': None, 'source': 'none'}

    async def _fetch_from_placeholder(self, server) -> dict[str, Any]:
        """通过占位符 API 服务采集 TPS / MSPT。"""
        config = self._config
        placeholder_service = self._placeholder_service()
        if placeholder_service is None:
            return {'tps': None, 'mspt': None}
        get_value = getattr(placeholder_service, 'get', None)
        if get_value is None:
            logger.debug('Placeholder service has no get(), skip placeholder source.')
            return {'tps': None, 'mspt': None}
        tps, mspt = None, None
        if config.placeholder_tps:
            raw = await self._safe_placeholder_get(get_value, config.placeholder_tps, server.self_id)
            tps = self._to_float(raw)
        if config.placeholder_mspt:
            raw = await self._safe_placeholder_get(get_value, config.placeholder_mspt, server.self_id)
            mspt = self._to_float(raw)
        return {'tps': tps, 'mspt': mspt}

    @staticmethod
    async def _safe_placeholder_get(get_value, placeholder: str, server_name: str):
        """安全调用占位符服务 get()，失败返回 None。"""
        try:
            return await get_value(placeholder, server_flag=server_name)
        except Exception as error:
            logger.warning(f'Placeholder fetch [{placeholder}] on [{server_name}] failed: {error}')
            return None

    # ===== 解析辅助 =====

    @classmethod
    def _parse_value(cls, output: str, custom_pattern: str, default_pattern: re.Pattern) -> float | None:
        """按自定义正则（优先）或内置默认正则解析单个指标值。"""
        patterns: list[re.Pattern | str] = [custom_pattern] if custom_pattern else []
        patterns.append(default_pattern)
        for pattern in patterns:
            try:
                compiled = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, re.IGNORECASE)
            except re.error:
                logger.warning(f'Invalid performance regex, skipped: {pattern}')
                continue
            match = compiled.search(output)
            if match and match.lastindex:
                number = cls._to_float(match.group(match.lastindex))
                if number is not None:
                    return number
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """将文本/数值安全转为非负 float，失败返回 None。"""
        if value is None:
            return None
        text = str(value).strip().replace(',', '')
        # 去掉可能尾随的单位（ms / tps 等字母），仅保留数字部分
        text = re.sub(r'[a-zA-Z]+\s*$', '', text)
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None
        return number if number >= 0 else None

    @staticmethod
    def _resolve_server(server_service, server_flag: str | int | None):
        """解析目标服务器，未指定时取第一台在线服务器。"""
        if server_flag:
            return server_service.get_server(server_flag)
        return next(iter(server_service.servers.values()), None)

    @staticmethod
    def _collect_target_servers(server_service, server_flag: str) -> list:
        """返回监控目标服务器列表：未指定时取全部已连接服务器。"""
        if server_flag:
            server = server_service.get_server(server_flag)
            return [server] if server is not None else []
        return list(server_service.servers.values())

    @staticmethod
    def _rule_matches(rule, server_name: str) -> bool:
        """判断阈值规则是否作用于指定服务器（空 server 作用于全部）。"""
        return not rule.server or rule.server == server_name

    def _build_violations(self, server_name: str, result: dict, rules: list) -> list[str]:
        """依据规则构造越界告警消息，应用重复告警与冷却期。"""
        config = self._config
        tps, mspt = result['tps'], result['mspt']
        violations: list[str] = []
        for rule in rules:
            if rule.min_tps > 0 and tps is not None and tps < rule.min_tps:
                violations.append(f'[{server_name}] TPS 过低：{tps:.1f} < {rule.min_tps:g}')
            if rule.max_mspt > 0 and mspt is not None and mspt > rule.max_mspt:
                violations.append(f'[{server_name}] MSPT 过高：{mspt:.1f} > {rule.max_mspt:g}')
        if not violations:
            self._cooldowns.pop(server_name, None)
            return []
        if not config.alert_repeat:
            now = time.monotonic()
            if now < self._cooldowns.get(server_name, 0.0):
                return []
            self._cooldowns[server_name] = now + config.monitor_interval
        return violations

    # ===== 定时监控调度 =====

    async def _monitor_loop(self) -> None:
        """周期执行监控采集，随扩展生命周期运行。"""
        config = self._config
        while True:
            await asyncio.sleep(config.monitor_interval)
            try:
                await self.monitor_round()
            except Exception as error:
                logger.warning(f'Performance monitor round failed: {error}')

    # ===== 告警发送 =====

    async def _send_alert(self, message: str) -> None:
        """向机器人的消息群发送告警消息。"""
        sent = await send_message_to_groups(message)
        if sent:
            logger.info('Sent performance alert to message groups.')
        else:
            logger.warning('Failed to send performance alert to message groups.')

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """构造无数据结果。"""
        return {'server': '', 'tps': None, 'mspt': None, 'source': 'none'}
