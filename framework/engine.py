"""
接口自动化测试框架 - 核心执行引擎

负责：
1. 从 YAML 文件加载测试用例
2. 基于依赖关系进行拓扑排序
3. 执行 HTTP 请求（模板渲染 → 发送请求 → 断言验证 → 变量提取）
4. 数据驱动参数化执行
5. 依赖失败跳过
"""

import logging  # 导入日志模块
import time  # 导入时间模块，用于测量请求耗时
from collections import deque  # 导入双端队列，用于拓扑排序
from typing import Any, Dict, List, Optional  # 导入类型注解

import json  # 导入JSON模块，用于JSON处理

import requests  # 导入HTTP请求库
import yaml  # 导入YAML解析库

from framework.models import (  # 导入数据模型类
    Assertion,  # 断言模型
    ExecutionContext,  # 执行上下文模型
    TestCase,  # 测试用例模型
    TestResult,  # 测试结果模型
)
from framework.config_loader import get_config  # 导入配置加载函数
from framework.extractor import (  # 导入变量提取相关函数
    extract_variables,  # 变量提取函数
    render_data,  # 数据渲染函数
    merge_data_params,  # 数据参数合并函数
)
from framework.assertions import validate_assertions  # 导入断言验证函数

# 模块级日志记录器
logger = logging.getLogger(__name__)  # 创建模块级日志记录器


class DependencyError(Exception):  # 定义依赖关系异常类
    """依赖关系异常（如循环依赖）"""  # 异常类的文档字符串
    pass  # 空类体


class TestEngine:  # 定义核心测试执行引擎类
    """核心测试执行引擎"""  # 类的文档字符串

    def __init__(self, env_name: str = "dev"):  # 初始化方法，接收环境名称参数
        """
        初始化引擎，加载环境配置，创建 ExecutionContext

        Args:
            env_name: 环境名称，对应 config/environments/{env_name}.yaml
        """
        logger.info("初始化测试引擎，环境: %s", env_name)  # 记录初始化日志
        # 加载环境配置
        config = get_config(env_name)  # 获取环境配置
        # 创建执行上下文
        self.context = ExecutionContext(  # 创建 ExecutionContext 实例
            variables=config.get("variables", {}),  # 初始化变量字典
            env_config=config,  # 设置环境配置
            results=[],  # 初始化结果列表
        )
        # 记录标记为 skip 的用例 ID
        self._skip_cases: set = set()  # 初始化跳过用例ID集合

    # ------------------------------------------------------------------
    # 用例加载
    # ------------------------------------------------------------------

    def load_testcases(self, case_file: str) -> List[TestCase]:  # 从YAML文件加载测试用例
        """
        从 YAML 文件加载用例，解析为 TestCase 对象列表

        Args:
            case_file: YAML 用例文件路径

        Returns:
            TestCase 对象列表
        """
        logger.info("加载用例文件: %s", case_file)  # 记录加载日志

        with open(case_file, "r", encoding="utf-8") as f:  # 打开YAML文件
            raw = yaml.safe_load(f)  # 解析YAML内容

        # 支持两种 YAML 顶层格式：
        # 1. 直接列表: [{id, name, ...}, ...]
        # 2. test_suite 包装: {test_suite: {name, variables, ...}, testcases: [...]}
        if isinstance(raw, dict):  # 检查是否为字典格式
            if "testcases" not in raw:  # 检查是否包含testcases字段
                raise ValueError(  # 格式错误时抛出异常
                    f"用例文件格式错误: dict 格式必须包含 'testcases' 字段"  # 异常消息
                )
            case_list = raw["testcases"]  # 提取testcases列表

            # 读取 test_suite 元数据
            suite_meta = raw.get("test_suite", {})  # 获取测试套件元数据
            if isinstance(suite_meta, dict):  # 检查是否为字典
                suite_name = suite_meta.get("name", "")  # 获取套件名称
                if suite_name:  # 如果有套件名称
                    logger.info("测试套件: %s", suite_name)  # 记录套件名称
                # 将 test_suite.variables 合并到全局变量池
                suite_vars = suite_meta.get("variables", {})  # 获取套件变量
                if isinstance(suite_vars, dict):  # 检查是否为字典
                    for k, v in suite_vars.items():  # 遍历变量
                        self.context.set_variable(k, v)  # 设置变量到上下文
                    if suite_vars:  # 如果有变量
                        logger.info("已加载套件级变量: %d 个", len(suite_vars))  # 记录变量数量
        elif isinstance(raw, list):  # 如果是列表格式
            case_list = raw  # 直接使用列表
        else:  # 其他格式
            raise ValueError(  # 抛出格式错误异常
                f"用例文件格式错误，期望 list 或 dict，实际: {type(raw).__name__}"  # 异常消息
            )

        if not isinstance(case_list, list):  # 检查testcases是否为列表
            raise ValueError(  # 格式错误时抛出异常
                f"'testcases' 字段必须是列表，实际: {type(case_list).__name__}"  # 异常消息
            )

        testcases: List[TestCase] = []  # 初始化测试用例列表
        # 重置 skip 记录
        self._skip_cases.clear()  # 清空跳过用例记录
        for item in case_list:  # 遍历每个用例项
            tc = self._parse_testcase(item)  # 解析用例字典为TestCase对象
            if item.get("skip", False):  # 检查是否标记为跳过
                self._skip_cases.add(tc.id)  # 将用例ID添加到跳过集合
            testcases.append(tc)  # 将解析后的用例添加到列表

        logger.info("共加载 %d 个用例", len(testcases))  # 记录加载的用例数量
        return testcases  # 返回测试用例列表

    @staticmethod  # 静态方法装饰器
    def _parse_testcase(data: dict) -> TestCase:  # 将用例字典解析为TestCase对象
        """将单个用例 dict 转为 TestCase 对象"""  # 方法文档字符串
        # 解析断言列表
        assertions = []  # 初始化断言列表
        for a in data.get("assertions", []):  # 遍历断言数据
            assertions.append(Assertion(  # 创建Assertion对象并添加到列表
                type=a["type"],  # 断言类型
                path=a.get("path"),  # JSON路径
                operator=a.get("operator", "equals"),  # 操作符，默认为equals
                expected=a.get("expected"),  # 期望值
            ))

        return TestCase(  # 创建并返回TestCase对象
            id=data["id"],  # 用例ID
            name=data["name"],  # 用例名称
            method=data["method"],  # HTTP方法
            url=data["url"],  # 请求URL
            headers=data.get("headers", {}),  # 请求头，默认空字典
            body=data.get("body"),  # 请求体
            query_params=data.get("query_params", {}),  # 查询参数，默认空字典
            assertions=assertions,  # 断言列表
            extract=data.get("extract", {}),  # 变量提取规则，默认空字典
            depends_on=data.get("depends_on", []),  # 依赖用例ID列表，默认空列表
            data_driven=data.get("data_driven"),  # 数据驱动参数
            timeout=data.get("timeout"),  # 超时时间
        )

    # ------------------------------------------------------------------
    # 拓扑排序（Kahn 算法）
    # ------------------------------------------------------------------

    def topological_sort(self, testcases: List[TestCase]) -> List[TestCase]:  # 拓扑排序方法
        """
        根据 depends_on 字段进行拓扑排序，确定执行顺序。
        使用 Kahn 算法，检测循环依赖并报错。

        Args:
            testcases: 待排序的 TestCase 列表

        Returns:
            排序后的 TestCase 列表

        Raises:
            DependencyError: 存在循环依赖时抛出
        """
        # 构建 id -> TestCase 映射
        id_map: Dict[str, TestCase] = {tc.id: tc for tc in testcases}  # 创建ID到用例的映射

        # 计算每个节点的入度，以及邻接表（依赖边）
        in_degree: Dict[str, int] = {tc.id: 0 for tc in testcases}  # 初始化入度字典
        # dependents[A] = [B, C] 表示 B、C 依赖 A（A 执行完才能执行 B、C）
        dependents: Dict[str, List[str]] = {tc.id: [] for tc in testcases}  # 初始化依赖关系字典

        for tc in testcases:  # 遍历每个测试用例
            for dep_id in tc.depends_on:  # 遍历每个依赖的ID
                if dep_id not in id_map:  # 检查依赖的用例是否存在
                    raise DependencyError(  # 不存在则抛出依赖错误
                        f"用例 '{tc.id}' 依赖的用例 '{dep_id}' 不存在"  # 异常消息
                    )
                dependents[dep_id].append(tc.id)  # 将当前用例添加到依赖者的列表
                in_degree[tc.id] += 1  # 当前用例入度加1

        # Kahn 算法：从入度为 0 的节点开始
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])  # 初始化队列，放入所有入度为0的节点
        sorted_ids: List[str] = []  # 初始化排序结果列表

        while queue:  # 当队列不为空时循环
            current = queue.popleft()  # 从队列左侧取出一个节点
            sorted_ids.append(current)  # 将节点添加到排序结果
            for dependent_id in dependents[current]:  # 遍历当前节点的所有依赖者
                in_degree[dependent_id] -= 1  # 依赖者入度减1
                if in_degree[dependent_id] == 0:  # 如果入度变为0
                    queue.append(dependent_id)  # 将依赖者加入队列

        if len(sorted_ids) != len(testcases):  # 如果排序结果数量与用例总数不符
            raise DependencyError(  # 说明存在循环依赖
                "检测到循环依赖！以下用例存在循环: "  # 异常消息前缀
                + str([tc.id for tc in testcases if tc.id not in sorted_ids])  # 列出循环用例ID
            )

        sorted_cases = [id_map[cid] for cid in sorted_ids]  # 根据排序后的ID列表获取对应的用例对象
        logger.info("拓扑排序完成，执行顺序: %s", sorted_ids)  # 记录排序结果
        return sorted_cases  # 返回排序后的用例列表

    # ------------------------------------------------------------------
    # 模板渲染辅助方法
    # ------------------------------------------------------------------

    def _render(self, data: Any, extra_variables: Optional[dict] = None) -> Any:  # 模板渲染辅助方法
        """
        渲染模板数据，自动注入全局配置变量和数据驱动参数

        将环境配置中的顶层变量（base_url, timeout 等）自动注入变量池，
        然后调用 render_data 递归渲染 dict/list/str 中的 Jinja2 模板。

        Args:
            data: 待渲染的数据（str/dict/list 等任意类型）
            extra_variables: 额外变量（如数据驱动参数），会叠加到变量池

        Returns:
            渲染后的数据
        """
        # 基础变量池：全局变量
        variables = self.context.get_all_variables()  # 获取所有全局变量
        # 注入环境配置中的顶层变量（base_url, timeout, verify_ssl 等）
        env_config = self.context.env_config  # 获取环境配置
        for key in ("base_url", "timeout", "verify_ssl"):  # 遍历需要注入的配置项
            if key in env_config:  # 如果配置项存在
                variables.setdefault(key, env_config[key])  # 设置默认值（不覆盖已有值）
        # 叠加额外变量（数据驱动参数等）
        if extra_variables:  # 如果有额外变量
            variables.update(extra_variables)  # 更新变量字典
        return render_data(data, variables)  # 渲染模板数据并返回

    # ------------------------------------------------------------------
    # 单用例执行
    # ------------------------------------------------------------------

    def execute_single(self, test_case: TestCase, data_params: Optional[dict] = None) -> TestResult:  # 执行单个测试用例
        """
        执行单个用例：
        1. 渲染模板变量（url, headers, body, query_params）
        2. 发送 HTTP 请求
        3. 验证断言
        4. 提取变量存入 context
        5. 返回 TestResult

        Args:
            test_case: 要执行的测试用例
            data_params: 数据驱动参数（可选），会合并到变量池

        Returns:
            TestResult 执行结果
        """
        logger.info("执行用例: [%s] %s", test_case.id, test_case.name)  # 记录执行日志

        # 将数据驱动参数合并到全局变量池，供后续用例使用
        if data_params:  # 如果有数据驱动参数
            for k, v in data_params.items():  # 遍历参数字典
                self.context.set_variable(k, v)  # 设置变量到上下文

        try:  # 开始异常捕获
            # ---- 1. 渲染模板变量（通过 _render 自动注入全局配置变量）----
            rendered_url = self._render(test_case.url, extra_variables=data_params)  # 渲染请求URL
            rendered_body = self._render(test_case.body, extra_variables=data_params)  # 渲染请求体
            rendered_params = self._render(test_case.query_params, extra_variables=data_params)  # 渲染查询参数

            # headers：先分别渲染环境级和用例级，再合并（用例级覆盖环境级）
            env_headers = self.context.env_config.get("headers", {})  # 获取环境级请求头
            rendered_env_headers = render_data(env_headers, self.context.get_all_variables())  # 渲染环境级请求头
            rendered_case_headers = self._render(test_case.headers, extra_variables=data_params)  # 渲染用例级请求头
            merged_headers = {**rendered_env_headers, **rendered_case_headers}  # 合并请求头，用例级覆盖环境级

            # ---- 2. 发送 HTTP 请求 ----
            method = test_case.method.upper()  # 将HTTP方法转换为大写
            # 超时：用例级 > 环境配置
            timeout = test_case.timeout or self.context.env_config.get("timeout", 30)  # 设置超时时间，优先使用用例级配置
            verify_ssl = self.context.env_config.get("verify_ssl", True)  # 获取SSL验证设置

            # 记录请求详情（info 级别，方便排查问题）
            logger.info(">>> 请求: %s %s", method, rendered_url)  # 记录请求方法和URL
            logger.info(">>> Headers: %s", merged_headers)  # 记录请求头
            if rendered_body is not None:  # 如果有请求体
                logger.info(">>> Body: %s", rendered_body)  # 记录请求体
            if rendered_params:  # 如果有查询参数
                logger.info(">>> Params: %s", rendered_params)  # 记录查询参数

            # 重试配置：从环境配置读取，默认 0（不重试，仅执行一次）
            max_retries = self.context.env_config.get("retry", 0)  # 获取最大重试次数

            start_time = time.time()  # 记录请求开始时间

            # 构建请求参数
            req_kwargs: Dict[str, Any] = {  # 构建requests请求参数字典
                "method": method,  # HTTP方法
                "url": rendered_url,  # 请求URL
                "headers": merged_headers,  # 请求头
                "params": rendered_params if rendered_params else None,  # 查询参数，为空则传None
                "timeout": timeout,  # 超时时间
                "verify": verify_ssl,  # SSL验证
            }

            # 根据 body 类型正确编码请求体
            if rendered_body is not None:  # 如果有请求体
                if isinstance(rendered_body, (dict, list)):  # dict/list类型
                    # dict/list：使用 json= 参数，requests 自动序列化并设置 Content-Type
                    req_kwargs["json"] = rendered_body  # 使用json参数
                elif isinstance(rendered_body, str):  # 字符串类型
                    # 字符串：检查 Content-Type 决定编码方式
                    content_type = merged_headers.get("Content-Type", "")  # 获取Content-Type
                    if "json" in content_type.lower():  # 如果是JSON类型
                        # JSON 字符串：用 data= 发送原始 JSON 文本
                        req_kwargs["data"] = rendered_body.encode("utf-8")  # 编码为UTF-8字节
                    else:  # 非JSON类型
                        req_kwargs["data"] = rendered_body  # 直接使用字符串
                else:  # 其他类型
                    req_kwargs["data"] = rendered_body  # 直接赋值

            # 带重试的请求执行
            last_exception = None  # 记录最后一次异常
            response = None  # 初始化响应对象
            for attempt in range(max_retries + 1):  # 循环尝试（包含第一次）
                try:  # 捕获请求异常
                    response = requests.request(**req_kwargs)  # 发送HTTP请求
                    break  # 请求成功，跳出重试循环
                except (requests.exceptions.ConnectionError,  # 捕获连接错误
                        requests.exceptions.Timeout) as e:  # 或超时错误
                    last_exception = e  # 记录异常
                    if attempt < max_retries:  # 如果还有重试次数
                        logger.warning(  # 记录警告日志
                            "用例 [%s] 第 %d/%d 次请求失败，正在重试: %s",  # 日志消息
                            test_case.id, attempt + 1, max_retries + 1, str(e),  # 用例ID、当前次数、总次数、错误信息
                        )

            end_time = time.time()  # 记录请求结束时间
            response_time = end_time - start_time  # 计算响应耗时

            # 如果所有重试都失败了，抛出最后一次的异常
            if response is None:  # 如果响应为空（所有重试都失败）
                raise last_exception  # 抛出最后一次异常

            # 记录响应详情（info 级别）
            logger.info(  # 记录响应状态码和耗时
                "<<< 响应: status=%s, time=%.3fs",  # 响应日志格式
                response.status_code, response_time,  # 状态码和响应时间
            )
            # 解析响应体
            try:  # 尝试解析JSON
                response_body = response.json()  # 解析为JSON对象
            except (ValueError, Exception):  # 解析失败
                response_body = response.text  # 退回使用原始文本
            logger.info("<<< Body: %s", response_body)  # 记录响应体

            # ---- 3. 验证断言 ----
            response_data = {  # 构造响应数据字典
                "status_code": response.status_code,  # 状态码
                "body": response_body,  # 响应体
                "headers": dict(response.headers),  # 响应头
                "response_time": response_time,  # 响应时间
            }

            assertion_results = validate_assertions(test_case.assertions, response_data)  # 执行断言验证
            all_passed = all(ar.passed for ar in assertion_results)  # 检查所有断言是否通过

            # ---- 4. 提取变量 ----
            if test_case.extract:  # 如果有变量提取规则
                for var_name, rule in test_case.extract.items():  # 遍历提取规则
                    if isinstance(rule, str):  # 如果规则是字符串
                        # 格式一：{"token": "$.data.token"}
                        jsonpath_expr = rule  # 直接使用字符串作为JSONPath表达式
                        target_var = var_name  # 变量名即为目标变量
                    elif isinstance(rule, dict):  # 如果规则是字典
                        # 格式二：{"token": {"jsonpath": "$.data.token", "rename": "auth_token"}}
                        jsonpath_expr = rule.get("jsonpath", "")  # 获取JSONPath表达式
                        target_var = rule.get("rename", var_name)  # 获取重命名后的变量名
                    else:  # 不支持的格式
                        logger.warning("变量 '%s' 的提取规则格式不支持，跳过", var_name)  # 记录警告
                        continue  # 跳过该变量

                    extracted = extract_variables(response_body, {target_var: jsonpath_expr})  # 提取变量
                    for name, value in extracted.items():  # 遍历提取结果
                        self.context.set_variable(name, value)  # 将变量存入上下文
                        logger.debug("变量已存入: %s = %s", name, value)  # 记录调试日志

            # ---- 5. 构造结果 ----
            result = TestResult(  # 创建测试结果对象
                test_case=test_case,  # 关联的测试用例
                passed=all_passed,  # 是否通过
                status_code=response.status_code,  # 响应状态码
                response_body=response_body,  # 响应体
                response_headers=dict(response.headers),  # 响应头
                response_time=response_time,  # 响应时间
                assertion_results=assertion_results,  # 断言结果列表
                data_params=data_params,  # 数据驱动参数
            )

        except requests.exceptions.Timeout as e:  # 捕获请求超时异常
            logger.error("用例 [%s] 请求超时: %s", test_case.id, str(e))  # 记录错误日志
            result = TestResult(  # 创建失败的结果对象
                test_case=test_case,  # 关联的测试用例
                passed=False,  # 标记为失败
                error=f"请求超时: {str(e)}",  # 错误信息
                data_params=data_params,  # 数据驱动参数
            )
        except requests.exceptions.ConnectionError as e:  # 捕获连接错误异常
            logger.error("用例 [%s] 连接错误: %s", test_case.id, str(e))  # 记录错误日志
            result = TestResult(  # 创建失败的结果对象
                test_case=test_case,  # 关联的测试用例
                passed=False,  # 标记为失败
                error=f"连接错误: {str(e)}",  # 错误信息
                data_params=data_params,  # 数据驱动参数
            )
        except requests.exceptions.RequestException as e:  # 捕获其他请求异常
            logger.error("用例 [%s] 请求异常: %s", test_case.id, str(e))  # 记录错误日志
            result = TestResult(  # 创建失败的结果对象
                test_case=test_case,  # 关联的测试用例
                passed=False,  # 标记为失败
                error=f"请求异常: {str(e)}",  # 错误信息
                data_params=data_params,  # 数据驱动参数
            )
        except Exception as e:  # 捕获所有其他异常
            logger.error("用例 [%s] 执行异常: %s", test_case.id, str(e))  # 记录错误日志
            result = TestResult(  # 创建失败的结果对象
                test_case=test_case,  # 关联的测试用例
                passed=False,  # 标记为失败
                error=f"执行异常: {str(e)}",  # 错误信息
                data_params=data_params,  # 数据驱动参数
            )

        return result  # 返回测试结果

    # ------------------------------------------------------------------
    # 数据驱动执行
    # ------------------------------------------------------------------

    def execute_data_driven(self, test_case: TestCase) -> List[TestResult]:  # 数据驱动执行方法
        """
        数据驱动执行：
        如果 test_case.data_driven 不为空，循环每组参数执行。
        每次执行前将 data_params 合并到变量池。

        Args:
            test_case: 包含 data_driven 数据的测试用例

        Returns:
            多个 TestResult 的列表
        """
        results: List[TestResult] = []  # 初始化结果列表

        if not test_case.data_driven:  # 如果没有数据驱动参数
            # 没有数据驱动参数，正常执行一次
            result = self.execute_single(test_case)  # 直接执行一次
            results.append(result)  # 将结果添加到列表
            return results  # 返回结果列表

        logger.info(  # 记录数据驱动执行日志
            "数据驱动执行: 用例 [%s]，共 %d 组参数",  # 日志消息
            test_case.id, len(test_case.data_driven),  # 用例ID和参数组数
        )

        for idx, data_params in enumerate(test_case.data_driven):  # 遍历每组数据驱动参数
            logger.info(  # 记录当前参数组日志
                "数据驱动: 用例 [%s] 第 %d/%d 组参数",  # 日志消息
                test_case.id, idx + 1, len(test_case.data_driven),  # 用例ID、当前索引、总组数
            )
            result = self.execute_single(test_case, data_params=data_params)  # 执行用例并传入参数
            results.append(result)  # 将结果添加到列表

        return results  # 返回所有结果

    # ------------------------------------------------------------------
    # 完整执行流程
    # ------------------------------------------------------------------

    def run(self, case_file: str) -> ExecutionContext:  # 完整执行流程方法
        """
        完整执行流程：
        1. 加载用例
        2. 拓扑排序
        3. 循环执行每个用例（判断是否数据驱动）
        4. 依赖用例失败时跳过后续依赖用例
        5. 返回完整的 ExecutionContext（含所有结果）

        Args:
            case_file: YAML 用例文件路径

        Returns:
            包含所有执行结果的 ExecutionContext
        """
        logger.info("=" * 60)  # 记录分隔线
        logger.info("开始执行测试: %s", case_file)  # 记录开始执行日志
        logger.info("=" * 60)  # 记录分隔线

        # 1. 加载用例
        testcases = self.load_testcases(case_file)  # 加载测试用例文件

        # 2. 拓扑排序
        sorted_cases = self.topological_sort(testcases)  # 对用例进行拓扑排序

        # 记录每个用例的最终执行状态（passed/failed/skipped），用于依赖判断
        case_status: Dict[str, bool] = {}  # 用例状态字典

        # 3. 循环执行
        for tc in sorted_cases:  # 遍历排序后的用例
            # 检查用例是否标记为 skip
            if tc.id in self._skip_cases:  # 如果用例在跳过集合中
                logger.info("用例 [%s] 已标记为 skip，跳过执行", tc.id)  # 记录跳过日志
                skipped_result = TestResult(  # 创建跳过的测试结果
                    test_case=tc,  # 关联的测试用例
                    passed=False,  # 标记为失败
                    error="用例已标记跳过",  # 错误信息
                )
                self.context.results.append(skipped_result)  # 将结果添加到上下文
                case_status[tc.id] = False  # 记录用例状态为失败
                continue  # 跳过后续代码

            # 4. 检查依赖用例是否全部通过
            skip = False  # 初始化跳过标志
            if tc.depends_on:  # 如果有依赖用例
                for dep_id in tc.depends_on:  # 遍历依赖的用例ID
                    if not case_status.get(dep_id, False):  # 如果依赖用例未通过
                        logger.warning(  # 记录警告日志
                            "用例 [%s] 被跳过: 依赖用例 '%s' 未通过",  # 日志消息
                            tc.id, dep_id,  # 用例ID和依赖用例ID
                        )
                        skip = True  # 设置跳过标志
                        break  # 跳出循环

            if skip:  # 如果需要跳过
                # 标记为跳过
                skipped_result = TestResult(  # 创建跳过的测试结果
                    test_case=tc,  # 关联的测试用例
                    passed=False,  # 标记为失败
                    error="依赖用例失败",  # 错误信息
                )
                self.context.results.append(skipped_result)  # 将结果添加到上下文
                case_status[tc.id] = False  # 记录用例状态为失败
                continue  # 跳过后续代码

            # 判断是否数据驱动
            if tc.data_driven:  # 如果有数据驱动参数
                results = self.execute_data_driven(tc)  # 执行数据驱动执行
                # 数据驱动：所有参数组都通过才算通过
                all_passed = all(r.passed for r in results)  # 检查所有结果是否通过
                self.context.results.extend(results)  # 将结果添加到上下文
                case_status[tc.id] = all_passed  # 记录用例状态
            else:  # 非数据驱动
                result = self.execute_single(tc)  # 直接执行单个用例
                self.context.results.append(result)  # 将结果添加到上下文
                case_status[tc.id] = result.passed  # 记录用例状态

        # 5. 汇总
        total = len(self.context.results)  # 计算总结果数
        passed = sum(1 for r in self.context.results if r.passed)  # 计算通过数
        failed = total - passed  # 计算失败数
        logger.info("=" * 60)  # 记录分隔线
        logger.info("执行完成: 共 %d 个结果，通过 %d，失败 %d", total, passed, failed)  # 记录执行完成日志
        logger.info("=" * 60)  # 记录分隔线

        return self.context  # 返回执行上下文
