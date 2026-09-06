"""Example 扩展配置模型。"""

from pydantic import BaseModel, Field


class ExampleConfig(BaseModel):
    """
    示例扩展的业务配置。

    字段会持久化到 `Config/Extensions/Example.toml`，并可在 WebUI
    扩展管理面板中动态生成表单编辑。使用 pydantic 约束（如 `ge=`）
    可实现输入校验，校验失败时不会写入配置。
    """

    # 问候语模板
    greeting: str = Field(default='你好，{name}！', description='问候语模板，`{name}` 会被使用者名替换')

    # 最大重复次数（必须为正整数）
    max_repeat: int = Field(default=3, ge=1, le=10, description='单次重复次数的上限')

    # 是否启用调试日志
    debug: bool = Field(default=False, description='是否输出调试日志')