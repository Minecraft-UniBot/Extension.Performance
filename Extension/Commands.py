"""
Example 示例指令。

演示 UniBot 指令开发的标准写法：
    - 主命令继承 `Command`，声明 name/description/usage
    - 子命令以嵌套 `SubCommand['父类']` 形式声明，框架自动发现并实例化
    - `declare()` 中调用 `register_arg` / `register_option` 注册参数
    - `handler()` 中通过 `Match` 参数读取用户输入并返回消息内容

⚠️ 关键经验（避免常见陷阱）：
    - 可选参数用 `register_option`（内部 `required=False`），必填用 `register_arg`
    - 渲染一段文本（贪婪吃多词）用 `register_option(..., multi=True)`
    - `Match` 参数务必同时检查 `available` 与 `result`，缺参/空值返回友好提示，
      否则指令可能"没反应"（静默跳过）
    - 不要依赖 `skip_for_unmatch` / 错误配置 option，缺参要在 handler 里主动兜底
"""

from typing import override

from Scripts.Extensions import Command, SubCommand, Match

from . import extension
from .Services import ExampleService


@extension.register_command
class ExampleCommand(Command):
    """示例命令：演示问候与重复文本。"""

    name = 'example'
    description = '示例命令，演示扩展指令开发。'
    usage = '/example <greet|repeat> [参数...]'

    class Greet(SubCommand['ExampleCommand']):
        """向使用者问好。"""

        name = 'greet'
        description = '向使用者问好'

        @override
        def declare(self) -> None:
            # 可选参数：不传则回退到配置默认 / handler 兜底
            self.register_option('target', str, default=None, description='问候对象，缺省使用当前使用者')

        @override
        async def handler(self, target: Match[str]):
            service = extension.api.get(ExampleService)
            if service is None:
                return '示例服务不可用，请检查扩展是否正常启用。'
            # 缺省问候对象时使用事件发送者（此处用占位演示，实际可经 event 取 sender）
            name = target.result if target.available and target.result else '陌生人'
            return service.compose_greeting(name)

    class Repeat(SubCommand['ExampleCommand']):
        """将文本重复输出多行。"""

        name = 'repeat'
        description = '将文本重复输出多行'

        @override
        def declare(self) -> None:
            # multi=True 把后续所有词合并为一个 list，用于"一段文本"类参数
            self.register_option('text', str, description='要重复的文本', multi=True)
            # 可选数值参数
            self.register_option('count', int, default=None, description='重复次数，缺省用配置默认值')

        @override
        async def handler(self, text: Match[list[str]], count: Match[int]):
            service = extension.api.get(ExampleService)
            if service is None:
                return '示例服务不可用，请检查扩展是否正常启用。'
            # 关键：同时检查 available 与 result，缺参或空值给出友好提示，避免静默无响应
            if not text.available or not text.result:
                return '请提供要重复的文本。'
            content = ' '.join(text.result).strip()
            count_value = count.result if count.available else None
            lines = service.repeat_text(content, count_value)
            return '\n'.join(lines)