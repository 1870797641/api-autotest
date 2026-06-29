"""
接口自动化测试框架 - 断言验证引擎
支持 status_code、jsonpath、response_time、regex 四种断言类型
"""

import re  # 导入正则表达式模块
import json  # 导入JSON处理模块
from typing import Any, List  # 导入类型提示模块

from jsonpath_ng import parse as jsonpath_parse  # 导入JSONPath解析器
from jsonpath_ng.exceptions import JsonPathParserError  # 导入JSONPath解析错误类

from framework.models import Assertion, AssertionResult  # 导入断言模型类


def validate_assertions(assertions: List[Assertion], response_data: dict) -> List[AssertionResult]:  # 验证所有断言规则的入口函数
    """
    验证所有断言规则

    Args:
        assertions: Assertion 对象列表
        response_data: 包含完整响应信息的字典，格式：
            {
                "status_code": 200,
                "body": {...},  # JSON响应体
                "headers": {...},
                "response_time": 0.5  # 秒
            }

    Returns:
        AssertionResult 对象列表
    """
    results = []  # 初始化结果列表
    for assertion in assertions:  # 遍历每个断言规则
        result = _validate_single(assertion, response_data)  # 验证单条断言
        results.append(result)  # 将结果添加到列表
    return results  # 返回所有断言结果


def _validate_single(assertion: Assertion, response_data: dict) -> AssertionResult:  # 验证单条断言规则
    """
    验证单条断言规则，根据断言类型分发到对应的处理函数

    Args:
        assertion: 单条断言规则
        response_data: 响应数据字典

    Returns:
        AssertionResult 断言结果
    """
    # 断言类型与处理函数的映射
    handlers = {  # 断言类型与处理函数的映射表
        "status_code": _assert_status_code,  # 状态码断言处理函数
        "jsonpath": _assert_jsonpath,  # JSONPath断言处理函数
        "response_time": _assert_response_time,  # 响应时间断言处理函数
        "regex": _assert_regex,  # 正则表达式断言处理函数
    }

    handler = handlers.get(assertion.type)  # 根据断言类型获取处理函数
    if handler is None:  # 如果未找到处理函数
        # 不支持的断言类型，直接标记失败
        return AssertionResult(  # 返回失败结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=None,  # 无实际值
            message=f"不支持的断言类型: {assertion.type}",  # 错误信息
        )

    try:
        return handler(assertion, response_data)  # 调用处理函数执行断言
    except Exception as e:
        # 任何未预期的异常都不抛出，而是记录到结果中
        return AssertionResult(  # 返回异常结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=None,  # 无实际值
            message=f"断言执行异常: {str(e)}",  # 异常信息
        )


# ======================== 各断言类型处理函数 ========================


def _assert_status_code(assertion: Assertion, response_data: dict) -> AssertionResult:  # 状态码断言处理函数
    """
    状态码断言：检查 HTTP 响应状态码是否符合预期

    Args:
        assertion: 断言规则，expected 默认为 200
        response_data: 响应数据

    Returns:
        AssertionResult
    """
    actual = response_data.get("status_code")  # 获取实际状态码
    expected = assertion.expected if assertion.expected is not None else 200  # 获取期望状态码，默认200

    passed = _compare(actual, expected, assertion.operator)  # 比较实际值与期望值
    message = (  # 构造断言结果消息
        f"状态码断言通过: 实际值={actual}"  # 通过时的消息
        if passed
        else f"状态码断言失败: 期望{assertion.operator} {expected}, 实际值={actual}"  # 失败时的消息
    )

    return AssertionResult(  # 返回断言结果
        assertion=assertion,  # 断言规则
        passed=passed,  # 断言是否通过
        actual_value=actual,  # 实际值
        message=message,  # 结果消息
    )


def _assert_jsonpath(assertion: Assertion, response_data: dict) -> AssertionResult:  # JSONPath断言处理函数
    """
    JSONPath 断言：使用 JSONPath 从响应体中提取值，然后与期望值比较

    Args:
        assertion: 断言规则，path 为 JSONPath 表达式
        response_data: 响应数据

    Returns:
        AssertionResult
    """
    body = response_data.get("body", {})  # 获取响应体，默认空字典
    path = assertion.path  # 获取JSONPath路径表达式

    # 解析 JSONPath 表达式
    try:
        expr = jsonpath_parse(path)  # 编译JSONPath表达式
    except (JsonPathParserError, Exception) as e:
        return AssertionResult(  # 返回解析错误结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=None,  # 无实际值
            message=f"JSONPath 解析错误: '{path}' -> {str(e)}",  # 错误信息
        )

    # 执行 JSONPath 查询
    matches = expr.find(body)  # 在响应体中执行JSONPath查询

    # exists 操作符特殊处理：只检查路径是否存在
    if assertion.operator == "exists":
        exists = len(matches) > 0  # 判断是否有匹配结果
        expected_exists = assertion.expected if assertion.expected is not None else True  # 获取期望的存在状态
        passed = exists == bool(expected_exists)  # 比较实际与期望的存在状态
        actual = matches[0].value if matches else None  # 取第一个匹配值
        message = (  # 构造结果消息
            f"JSONPath '{path}' 存在性检查通过"  # 通过时的消息
            if passed
            else f"JSONPath '{path}' 存在性检查失败: 期望存在={expected_exists}, 实际存在={exists}"  # 失败时的消息
        )
        return AssertionResult(  # 返回断言结果
            assertion=assertion,  # 断言规则
            passed=passed,  # 是否通过
            actual_value=actual,  # 实际值
            message=message,  # 结果消息
        )

    # 其他操作符：需要取到匹配值
    if not matches:
        return AssertionResult(  # 返回未匹配结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=None,  # 无实际值
            message=f"JSONPath '{path}' 未匹配到任何值",  # 错误信息
        )

    # 取第一个匹配值作为实际值
    actual = matches[0].value  # 提取第一个匹配值
    expected = assertion.expected  # 获取期望值

    passed = _compare(actual, expected, assertion.operator)  # 比较实际值与期望值
    message = (  # 构造结果消息
        f"JSONPath '{path}' 断言通过: 实际值={actual}"  # 通过时的消息
        if passed
        else f"JSONPath '{path}' 断言失败: 期望{assertion.operator} {expected}, 实际值={actual}"  # 失败时的消息
    )

    return AssertionResult(  # 返回断言结果
        assertion=assertion,  # 断言规则
        passed=passed,  # 是否通过
        actual_value=actual,  # 实际值
        message=message,  # 结果消息
    )


def _assert_response_time(assertion: Assertion, response_data: dict) -> AssertionResult:  # 响应时间断言处理函数
    """
    响应时间断言：检查响应时间是否在预期范围内（默认 lt，即小于预期值才通过）

    Args:
        assertion: 断言规则，operator 默认为 "lt"
        response_data: 响应数据

    Returns:
        AssertionResult
    """
    actual = response_data.get("response_time", 0.0)  # 获取实际响应时间，默认0.0秒
    expected = assertion.expected if assertion.expected is not None else 1.0  # 获取期望时间，默认1.0秒
    # 响应时间默认操作符为 lt（小于预期值才通过）
    operator = assertion.operator if assertion.operator != "equals" else "lt"  # 确定比较操作符

    passed = _compare(actual, expected, operator)  # 比较实际与期望时间
    message = (  # 构造结果消息
        f"响应时间断言通过: 实际耗时={actual}s"  # 通过时的消息
        if passed
        else f"响应时间断言失败: 期望{operator} {expected}s, 实际耗时={actual}s"  # 失败时的消息
    )

    return AssertionResult(  # 返回断言结果
        assertion=assertion,  # 断言规则
        passed=passed,  # 是否通过
        actual_value=actual,  # 实际值
        message=message,  # 结果消息
    )


def _assert_regex(assertion: Assertion, response_data: dict) -> AssertionResult:  # 正则表达式断言处理函数
    """
    正则表达式断言：对响应体文本进行正则匹配
    如果提供了 path，则先用 JSONPath 提取值再匹配；否则将整个 body 转为字符串匹配

    Args:
        assertion: 断言规则，expected 为正则表达式字符串
        response_data: 响应数据

    Returns:
        AssertionResult
    """
    body = response_data.get("body", "")  # 获取响应体，默认空字符串
    pattern = assertion.expected  # 获取正则表达式模式

    if pattern is None:
        return AssertionResult(  # 返回模式为空的错误结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=None,  # 无实际值
            message="正则断言失败: 未提供正则表达式(expected 为空)",  # 错误信息
        )

    # 如果指定了 path，先用 JSONPath 提取目标值
    if assertion.path:
        try:
            expr = jsonpath_parse(assertion.path)  # 编译JSONPath表达式
        except (JsonPathParserError, Exception) as e:
            return AssertionResult(  # 返回解析错误结果
                assertion=assertion,  # 断言规则
                passed=False,  # 断言失败
                actual_value=None,  # 无实际值
                message=f"JSONPath 解析错误: '{assertion.path}' -> {str(e)}",  # 错误信息
            )

        matches = expr.find(body)  # 执行JSONPath查询
        if not matches:
            return AssertionResult(  # 返回未匹配结果
                assertion=assertion,  # 断言规则
                passed=False,  # 断言失败
                actual_value=None,  # 无实际值
                message=f"正则断言失败: JSONPath '{assertion.path}' 未匹配到任何值",  # 错误信息
            )
        # 将提取到的值转为字符串进行正则匹配
        text = str(matches[0].value)  # 转换为字符串
    else:
        # 未指定 path，将整个 body 转为字符串
        text = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)  # 序列化为JSON字符串

    # 执行正则匹配
    try:
        match = re.search(pattern, text)  # 执行正则搜索
    except re.error as e:
        return AssertionResult(  # 返回正则语法错误结果
            assertion=assertion,  # 断言规则
            passed=False,  # 断言失败
            actual_value=text,  # 实际文本
            message=f"正则表达式错误: '{pattern}' -> {str(e)}",  # 错误信息
        )

    passed = match is not None  # 判断是否匹配成功
    matched_text = match.group(0) if match else None  # 提取匹配到的文本
    message = (  # 构造结果消息
        f"正则断言通过: 匹配到 '{matched_text}'"  # 通过时的消息
        if passed
        else f"正则断言失败: 表达式 '{pattern}' 未在文本中匹配到内容"  # 失败时的消息
    )

    return AssertionResult(  # 返回断言结果
        assertion=assertion,  # 断言规则
        passed=passed,  # 是否通过
        actual_value=matched_text,  # 匹配到的文本
        message=message,  # 结果消息
    )


# ======================== 通用比较函数 ========================


def _compare(actual: Any, expected: Any, operator: str) -> bool:  # 通用比较函数
    """
    根据操作符比较实际值与期望值

    Args:
        actual: 实际值
        expected: 期望值
        operator: 操作符字符串

    Returns:
        比较结果，True 表示断言通过
    """
    try:
        if operator == "equals":
            return actual == expected  # 相等比较

        elif operator == "not_equals":
            return actual != expected  # 不等比较

        elif operator == "contains":
            # 字符串包含 或 列表包含
            if isinstance(actual, (str, list)):
                return expected in actual  # 判断是否包含
            # 其他类型转为字符串后判断包含
            return str(expected) in str(actual)  # 转字符串后判断包含

        elif operator == "exists":
            # 存在性检查：actual 不为 None 即视为存在
            return actual is not None  # 判断值是否存在

        elif operator == "gt":
            return float(actual) > float(expected)  # 大于比较

        elif operator == "lt":
            return float(actual) < float(expected)  # 小于比较

        elif operator == "in":
            # 实际值在期望列表中
            if isinstance(expected, (list, tuple, set)):
                return actual in expected  # 判断是否在列表中
            return actual == expected  # 非列表类型退化为相等比较

        elif operator == "regex_match":
            # 将实际值转为字符串后进行正则匹配
            return re.search(str(expected), str(actual)) is not None  # 正则匹配

        else:
            # 未知操作符，默认使用 equals
            return actual == expected  # 未知操作符按相等处理

    except (TypeError, ValueError):
        # 类型不兼容时返回 False
        return False  # 类型错误返回断言失败
