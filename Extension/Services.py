"""Performance 内部性能采集辅助。

本模块不注册任何能力，仅供扩展本体内部复用。TPS/MSPT 采集、定时监控与阈值告警
逻辑收敛于此，由扩展实例在生命周期钩子中调用。
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

from Scripts.Extensions.Builtin.Services.Servers import ServerService
from Scripts.Extensions.Builtin.Services.Task import TaskService
from Scripts.Logging import logger
from Scripts.Utils import send_message_to_groups, strip_minecraft_color

from .Config import DEFAULT_MSPT_PATTERN, DEFAULT_TPS_PATTERN

if TYPE_CHECKING:
    from nonebot.adapters.minecraft import Bot

    from Scripts.Extensions import Extension

    from .Config import PerformanceConfig, Threshold

# 定时监控任务名（登记到机器人全局 TaskService，避免与其它任务重名）
_MONITOR_TASK_NAME = 'performance-monitor'

# 目标服务器参数取值：显式指定全部服务器
ALL_SERVERS_FLAG = '*'

# 内置默认正则：直接复用 Config 声明的默认字符串常量（单一来源），此处编译一次供回退使用
_DEFAULT_TPS_PATTERN = re.compile(DEFAULT_TPS_PATTERN, re.IGNORECASE)
_DEFAULT_MSPT_PATTERN = re.compile(DEFAULT_MSPT_PATTERN, re.IGNORECASE)


class PerformanceHelper:
    """TPS/MSPT 采集、定时监控与阈值告警的内部辅助类。"""

    def __init__(self, extension: Extension) -> None:
        self._extension = extension
        # 各服务器告警冷却截止时间（time.monotonic 相对时间）：{server_name: cooldown_end}
        self._cooldowns: dict[str, float] = {}

    # ===== 对外能力 =====

    async def start(self) -> None:
        """按配置启用定时监控任务。"""
        config = self._config
        if not config.monitor_enabled:
            return
        task_service = self._task_service()
        if task_service is None:
            logger.warning('TaskService unavailable, monitor not started.')
            return
        if not task_service.add(_MONITOR_TASK_NAME, self.monitor_round, config.monitor_interval):
            logger.warning(f'Monitor task {_MONITOR_TASK_NAME} could not be registered.')
            return
        logger.success('Performance monitor started.')

    async def stop(self) -> None:
        """停止定时监控任务并清空告警冷却状态。"""
        task_service = self._task_service()
        if task_service is not None:
            task_service.remove(_MONITOR_TASK_NAME)
        self._cooldowns.clear()
        logger.info('Performance monitor stopped.')

    async def fetch_many(self, server_flag: str | int | None = None) -> list[dict[str, Any]]:
        """
        查询一台或全部已连接服务器的 TPS / MSPT。

        传编号 / 名称时仅查询该服务器（不存在或未连接时返回空列表）；
        缺省或传 `*` 时并发查询全部已连接服务器，按 `/server` 的服务器列表顺序返回。

        每项为 `{'server': 名称, 'tps': float|None, 'mspt': float|None, 'source': 来源}`。
        """
        server_service = self._server_service()
        if server_service is None or not server_service.check_online():
            return []
        targets = self._resolve_targets(server_service, server_flag)
        if not targets:
            return []
        # 并发采集避免多服务器串行等待；gather 保持输入顺序，结果即与服务器列表顺序一致
        collected = await asyncio.gather(*(self._fetch_one(server) for _, server in targets))
        return [{**result, 'server': name} for (name, _), result in zip(targets, collected)]

    async def monitor_round(self) -> None:
        """执行一轮监控采集，并按阈值规则向消息群发送告警。"""
        config = self._config
        if not (config.monitor_enabled and config.thresholds):
            return
        server_service = self._server_service()
        if server_service is None or not server_service.check_online():
            return
        results = await self.fetch_many(config.monitor_server or None)
        for result in results:
            if result['tps'] is None and result['mspt'] is None:
                continue
            server_name = result['server']
            rules = [rule for rule in config.thresholds if self._rule_matches(rule, server_name)]
            for message in self._build_violations(server_name, result, rules):
                await self._send_alert(message)

    # ===== 采集实现 =====

    @property
    def _config(self) -> PerformanceConfig:
        """读取当前扩展配置。"""
        return self._extension.config.value

    def _server_service(self) -> ServerService | None:
        """获取内置服务器服务，缺失返回 None。"""
        return self._extension.api.get(ServerService)

    def _task_service(self) -> TaskService | None:
        """获取内置定时任务服务，缺失返回 None。"""
        return self._extension.api.get(TaskService)

    def _placeholder_service(self) -> Any | None:
        """按注册名获取占位符 API 服务（未安装时返回 None）。"""
        return self._extension.api.get('placeholder')

    async def _fetch_one(self, server: Bot) -> dict[str, Any]:
        """采集单台服务器的性能数据，依次尝试指令与占位符数据源。"""
        result = await self._fetch_from_command(server)
        if result['tps'] is None and self._config.placeholder_source_enabled:
            placeholder_result = await self._fetch_from_placeholder(server)
            placeholder_result['source'] = 'placeholder' if placeholder_result['tps'] is not None else 'none'
            result = placeholder_result
        return result

    async def _fetch_from_command(self, server: Bot) -> dict[str, Any]:
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

    async def _fetch_from_placeholder(self, server: Bot) -> dict[str, Any]:
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
    async def _safe_placeholder_get(get_value, placeholder: str, server_name: str) -> str | None:
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
    def _resolve_targets(server_service: ServerService, server_flag: str | int | None) -> list[tuple[str, Bot]]:
        """
        解析查询目标为 `(名称, 机器人)` 列表。

        传编号 / 名称时仅返回匹配的服务器（编号与 `/server` 展示的列表顺序一致，
        从 1 开始），缺省或传 `*` 时返回全部已连接服务器。
        """
        items = list(server_service.servers.items())
        if server_flag and str(server_flag).strip() != ALL_SERVERS_FLAG:
            bot = server_service.get_server(server_flag)
            if bot is None:
                return []
            for name, candidate in items:
                if candidate is bot:
                    return [(name, bot)]
            return [(bot.self_id, bot)]
        return items

    @staticmethod
    def _rule_matches(rule: Threshold, server_name: str) -> bool:
        """判断阈值规则是否作用于指定服务器（空 server 作用于全部）。"""
        return not rule.server or rule.server == server_name

    def _build_violations(self, server_name: str, result: dict[str, Any], rules: list[Threshold]) -> list[str]:
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

    # ===== 告警发送 =====

    async def _send_alert(self, message: str) -> None:
        """向机器人的消息群发送告警消息。"""
        sent = await send_message_to_groups(message)
        if sent:
            logger.info('Sent performance alert to message groups.')
        else:
            logger.warning('Failed to send performance alert to message groups.')
