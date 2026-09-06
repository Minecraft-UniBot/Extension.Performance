"""
Example 扩展包入口。

一个演示 UniBot 扩展开发流程的模板扩展：包含指令（command）、服务（api）与配置。
结构遵循标准多文件扩展布局，可直接打包发布到插件市场。

布局说明：
    Extension.toml    清单：声明类型、依赖与版本（市场上传以 zip 根目录包含它为准）
    __init__.py       入口：创建扩展实例并登记能力
    Config.py         配置模型（pydantic BaseModel）
    Commands.py       指令定义（Command + 嵌套 SubCommand）
    Services.py       服务实现（Service，供其它扩展复用）
"""

from Scripts.Extensions import Extension

from .Config import ExampleConfig

# 唯一扩展实例。config_model 声明配置模型，能力经实例装饰器登记；
# id/name/version 等元数据以 Extension.toml 为准，无需在此声明。
extension = Extension(config_model=ExampleConfig)

# 能力模块在扩展实例创建后导入，经相对导入获取同一实例。
# 注意导入顺序：先 Config（无依赖），再 Services / Commands（依赖 extension）。
from . import Commands, Services  # noqa: E402,F401