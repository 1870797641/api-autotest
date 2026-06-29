"""
接口自动化测试框架 - 配置管理模块
负责加载全局配置和环境配置，并提供统一的配置获取入口
"""

import copy  # 导入copy模块用于深拷贝操作
import os  # 导入操作系统模块提供系统交互功能
from pathlib import Path  # 导入Path类处理文件路径
from typing import Any, Dict  # 导入类型提示注解

import yaml  # 导入YAML解析库用于配置文件处理


# 项目根目录（framework 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 计算项目根目录路径
ENVIRONMENTS_DIR = PROJECT_ROOT / "config" / "environments"  # 构建环境配置文件目录路径
GLOBAL_CONFIG_PATH = PROJECT_ROOT / "config" / "global.yaml"  # 构建全局配置文件完整路径


class ConfigError(Exception):  # 定义配置错误异常类
    """配置相关异常"""
    pass  # 异常类体为空，继承Exception即可


def load_environment(env_name: str) -> Dict[str, Any]:  # 加载环境配置函数
    """
    加载指定环境的配置文件
    :param env_name: 环境名称（对应 config/environments/{env_name}.yaml）
    :return: 环境配置字典
    :raises ConfigError: 当配置文件不存在或解析失败时抛出
    """
    if not env_name:  # 检查环境名称参数是否为空
        raise ConfigError("环境名称不能为空")  # 参数为空时抛出异常

    env_file = ENVIRONMENTS_DIR / f"{env_name}.yaml"  # 构建环境配置文件路径

    # 检查配置文件是否存在
    if not env_file.exists():  # 检查配置文件是否存在
        available = [f.stem for f in ENVIRONMENTS_DIR.glob("*.yaml")]  # 获取所有可用环境名称列表
        raise ConfigError(  # 文件不存在时抛出异常
            f"环境配置文件不存在: {env_file}\n"
            f"可用环境: {available}"
        )

    try:  # 尝试读取并解析配置文件
        with open(env_file, "r", encoding="utf-8") as f:  # 以只读方式打开YAML文件
            config = yaml.safe_load(f)  # 安全加载YAML内容为字典
    except yaml.YAMLError as e:  # 捕获YAML解析错误
        raise ConfigError(f"环境配置文件解析失败 [{env_name}]: {e}")  # 解析失败时抛出异常

    return config if isinstance(config, dict) else {}  # 返回配置字典，非字典类型转为空字典


def load_global_config() -> Dict[str, Any]:  # 加载全局配置函数
    """
    加载全局默认配置
    :return: 全局配置字典，若文件不存在则返回空字典
    :raises ConfigError: 当配置文件解析失败时抛出
    """
    if not GLOBAL_CONFIG_PATH.exists():  # 检查全局配置文件是否存在
        # 全局配置是可选的，不存在时返回空字典
        return {}  # 文件不存在返回空字典

    try:  # 尝试读取并解析全局配置文件
        with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:  # 以只读方式打开YAML文件
            config = yaml.safe_load(f)  # 安全加载YAML内容为字典
    except yaml.YAMLError as e:  # 捕获YAML解析错误
        raise ConfigError(f"全局配置文件解析失败: {e}")  # 解析失败时抛出异常

    return config if isinstance(config, dict) else {}  # 返回配置字典，非字典类型转为空字典


def merge_config(global_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:  # 合并配置函数
    """
    合并全局配置与环境配置（深度合并，环境配置覆盖全局配置）
    :param global_config: 全局默认配置
    :param env_config: 环境配置（优先级更高）
    :return: 合并后的完整配置字典
    """
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:  # 内部深度合并函数
        """递归深度合并，override 中的值覆盖 base 中的同名键"""
        result = copy.deepcopy(base)  # 深拷贝基础配置作为结果
        for key, value in override.items():  # 遍历覆盖配置的每个键值对
            if (  # 检查是否两个值都是字典类型需要递归合并
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = _deep_merge(result[key], value)  # 递归合并嵌套字典
            else:
                result[key] = copy.deepcopy(value)  # 直接覆盖或添加新键值对
        return result  # 返回合并后的结果

    # 入参防御：避免传入 None
    base = global_config if isinstance(global_config, dict) else {}  # 确保基础配置为字典
    override = env_config if isinstance(env_config, dict) else {}  # 确保覆盖配置为字典

    return _deep_merge(base, override)  # 执行深度合并并返回结果


def get_config(env_name: str = "dev") -> Dict[str, Any]:  # 获取配置的统一入口函数
    """
    对外统一入口：加载并返回合并后的完整配置
    :param env_name: 环境名称，默认为 "dev"
    :return: 合并后的配置字典（环境配置覆盖全局默认值）
    """
    global_config = load_global_config()  # 加载全局配置
    env_config = load_environment(env_name)  # 加载指定环境配置
    return merge_config(global_config, env_config)  # 合并配置并返回结果
