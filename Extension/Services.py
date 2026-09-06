"""
Example 示例服务。

通过 `Service` 基类暴露可被指令或其它扩展复用的能力。
服务注册名 `name` 供 `extension.api.get(PlaceholderService)` 获取。
"""

from Scripts.Extensions import Service

from . import extension


@extension.register_service
class ExampleService(Service):
    """
    示例服务：暴露打招呼与文本处理能力。

    其它扩展通过 `extension.api.get(ExampleService)` 获取实例后调用。
    """

    # 服务注册名（缺省使用类名），全框架唯一
    name = 'example'

    # ===== 生命周期（可选覆盖） =====

    async def on_enable(self) -> None:
        """服务启动时调用，适合初始化外部资源、连接等。"""
        self._ready = True

    async def on_disable(self) -> None:
        """服务关闭时调用，适合释放外部资源。"""
        self._ready = False

    # ===== 公共能力 =====

    def compose_greeting(self, name: str) -> str:
        """
        根据配置生成问候语。

        演示如何读取扩展配置（`extension.config.value` 返回配置模型实例）。
        """
        config = extension.config.value
        return config.greeting.format(name=name)

    def repeat_text(self, text: str, count: int | None = None) -> list[str]:
        """
        将文本重复多行输出。

        未指定 count 时使用配置默认值，并受 `max_repeat` 上限约束。
        """
        config = extension.config.value
        count = config.max_repeat if count is None else count
        count = max(1, min(count, config.max_repeat))
        return [text] * count