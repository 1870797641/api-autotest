"""
=============================================================================
接口自动化测试框架 - 变量提取与模板渲染模块（extractor.py）
=============================================================================

【模块整体说明】
这个模块是整个测试框架的"数据处理中心"，负责四件非常重要的事情：

1. JSONPath 变量提取（extract_variables 函数）：
   - 当你发送一个 HTTP 请求后，服务器会返回一段 JSON 数据（响应体）
   - 有时候你需要从这段 JSON 里"抠出"某个值，比如用户ID、token 等
   - 这个函数就是用 JSONPath 表达式（类似 XPath，但专门用于 JSON）来提取这些值
   - 提取出来的值会存到一个"变量池"（字典）里，供后续用例使用

2. Jinja2 模板渲染（render_template 函数）：
   - 写测试用例时，很多值是动态的，比如 token、用户ID
   - 我们用 {{ 变量名 }} 这种占位符来表示"这里以后会被替换"
   - 这个函数就是把占位符替换成真实值的过程，叫做"渲染"

3. 递归渲染（render_data 函数）：
   - 实际测试中，headers、body、url 等都可能有占位符
   - 这些数据可能是字符串、字典、列表，甚至嵌套结构
   - 这个函数能递归地处理所有类型，把所有占位符都替换掉

4. 数据驱动参数合并（merge_data_params 函数）：
   - 数据驱动测试就是"同一套流程，用不同的数据跑多次"
   - 这个函数把每组测试数据合并到用例的变量池里

【依赖说明】
- logging：Python 标准库，用于记录日志（调试信息、警告、错误等）
- typing.Any：类型提示，表示"任意类型"
- jinja2：模板引擎库，用来处理 {{ 变量名 }} 这种模板语法
- jsonpath_ng：JSONPath 解析库，用来从 JSON 数据中提取值
"""

# ======================== 导入依赖 ========================

# 导入 Python 标准库 logging 模块
# logging 是 Python 内置的日志模块，可以记录不同级别的日志信息（DEBUG/INFO/WARNING/ERROR）
# 比 print() 更专业，可以控制日志级别、输出格式、输出目标等
import logging

# 从 typing 模块导入 Any
# Any 是 Python 的类型提示（Type Hint），表示"可以是任意类型"
# 类型提示不影响运行，但能让 IDE 提供更好的代码提示，也方便阅读代码
from typing import Any

# 从 jinja2 库导入三个组件：
# - BaseLoader：Jinja2 的模板加载器基类，BaseLoader() 表示不从文件加载，直接从字符串加载
# - Environment：Jinja2 的核心类，代表一个"模板环境"，控制模板的行为（如变量查找方式、未定义变量的处理等）
# - Undefined：Jinja2 的特殊类，当模板中引用了未定义的变量时，不会报错，而是返回空字符串
from jinja2 import BaseLoader, Environment, Undefined

# 从 jsonpath_ng 库导入 parse 函数，并重命名为 jsonpath_parse
# jsonpath_ng 是一个 JSONPath 解析库，可以用类似 "$.data.user.id" 的语法从 JSON 中提取值
# 用 "as jsonpath_parse" 重命名是为了避免和其他模块的 parse 函数冲突
from jsonpath_ng import parse as jsonpath_parse

# ======================== 模块级日志记录器 ========================

# 创建一个模块级别的日志记录器（logger）
# __name__ 是 Python 的特殊变量，值为当前模块的名称（如 "framework.extractor"）
# 用 __name__ 作为 logger 名称的好处：
#   1. 每个模块有独立的 logger，方便定位日志来源
#   2. 日志会按照模块层级组织（framework -> extractor），便于管理
#   3. 可以在不同模块设置不同的日志级别
logger = logging.getLogger(__name__)


# ======================== 函数1：从响应体中提取变量 ========================

def extract_variables(response_body: Any, extract_rules: dict) -> dict:
    """
    从 HTTP 响应体中按 JSONPath 规则提取变量

    【功能说明】
    这个函数的作用是：你告诉它"我要从响应中提取哪些值"，它就帮你提取出来。
    比如服务器返回了 {"data": {"user": {"id": 123, "name": "张三"}}}，
    你可以用 JSONPath "$.data.user.id" 来提取出 123。

    【参数说明】
    Args:
        response_body: JSON 响应体，通常是 dict 或 list 类型
            例如：{"code": 0, "data": {"token": "abc123"}}
        extract_rules: 提取规则字典，格式为 {"变量名": "$.jsonpath.表达式"}
            例如：{"my_token": "$.data.token"} 表示：
            - 用 JSONPath "$.data.token" 从响应体中提取值
            - 把提取到的值存到变量 "my_token" 中

    【返回值说明】
    Returns:
        提取到的变量字典，格式为 {"变量名": 提取到的值}
        例如：{"my_token": "abc123"}
        如果某个变量提取失败，值为 None，例如：{"my_token": None}
    """
    # 创建一个空字典，用来存放提取到的变量
    # 这个字典最终会作为函数的返回值
    extracted = {}

    # 遍历提取规则字典中的每一对"变量名"和"JSONPath 表达式"
    # .items() 方法会返回字典中所有的键值对（key-value pairs）
    # 例如 {"a": "$.x", "b": "$.y"}.items() 会产生 [("a", "$.x"), ("b", "$.y")]
    # for var_name, jsonpath_expr in ... 这种写法叫做"解包"（unpacking）
    # 每次循环会把键值对的两个值分别赋给 var_name 和 jsonpath_expr
    for var_name, jsonpath_expr in extract_rules.items():
        # 使用 try/except 进行异常处理
        # try 块中放可能出错的代码，如果出错就跳到 except 块处理
        # 这样即使某个变量的 JSONPath 写错了，也不会导致整个程序崩溃
        try:
            # 第一步：解析 JSONPath 表达式
            # jsonpath_parse() 会把字符串形式的 JSONPath（如 "$.data.id"）
            # 转换成一个可执行的 JSONPath 表达式对象
            # 类似于 re.compile() 把正则表达式字符串编译成正则对象
            parsed = jsonpath_parse(jsonpath_expr)

            # 第二步：在响应体中查找匹配的值
            # .find() 方法会在 response_body 中搜索所有匹配 JSONPath 表达式的值
            # 返回一个列表，列表中每个元素是一个 Match 对象（包含 .value 属性）
            matches = parsed.find(response_body)

            # 第三步：判断是否找到了匹配结果
            # if matches: 利用了 Python 的"真值测试"（truthiness）
            # 空列表 [] 被视为 False，非空列表被视为 True
            # 所以这里的意思是"如果匹配到了至少一个结果"
            if matches:
                # 取第一个匹配结果的值
                # matches[0] 是第一个 Match 对象，.value 是它匹配到的值
                # 为什么只取第一个？因为大多数情况下我们只关心第一个匹配结果
                extracted[var_name] = matches[0].value

                # 记录一条 DEBUG 级别的日志
                # DEBUG 是最低级别的日志，通常只在开发调试时显示
                # %s 是字符串格式化占位符，后面的参数会依次替换 %s
                logger.debug("变量提取成功: %s = %s", var_name, matches[0].value)
            else:
                # 如果没有匹配到任何结果，把变量值设为 None
                # None 是 Python 中表示"空值"的特殊对象
                extracted[var_name] = None

                # 记录一条 WARNING 级别的日志
                # WARNING 表示这是一个需要关注但不致命的问题
                # 使用多行字符串拼接（Python 会自动把括号内的多行字符串拼成一个字符串）
                logger.warning(
                    "变量提取失败: 变量 '%s' 的 JSONPath '%s' 未匹配到任何值",
                    var_name, jsonpath_expr
                )
        except Exception as e:
            # except Exception as e 会捕获所有类型的异常（错误）
            # as e 把异常对象赋值给变量 e，方便后续查看错误信息
            # 这里的"异常"可能是 JSONPath 表达式语法写错了，比如少了个点号

            # 即使出错，也要给变量赋一个默认值 None，防止后续代码报 KeyError
            extracted[var_name] = None

            # 记录警告日志，包含变量名、JSONPath 表达式和具体的错误信息
            # str(e) 把异常对象转成字符串，得到人类可读的错误描述
            logger.warning(
                "变量提取异常: 变量 '%s' 的 JSONPath '%s' 解析出错 - %s",
                var_name, jsonpath_expr, str(e)
            )

    # 返回包含所有提取到的变量的字典
    return extracted


# ======================== 函数2：渲染单个模板字符串 ========================

def render_template(template_str: str, variables: dict) -> str:
    """
    使用 Jinja2 渲染模板字符串中的变量占位符

    【功能说明】
    把包含 {{ 变量名 }} 的模板字符串中的占位符替换为实际值。
    例如：模板字符串 "Hello, {{ name }}!" 加上变量 {"name": "张三"}
         -> 渲染结果 "Hello, 张三!"

    【参数说明】
    Args:
        template_str: 包含 {{ var }} 占位符的模板字符串
            例如："Bearer {{ token }}" 或 "http://{{ host }}/api"
        variables: 变量字典，存储所有可用的变量及其值
            例如：{"token": "abc123", "host": "example.com"}

    【返回值说明】
    Returns:
        渲染后的字符串，所有占位符都被替换成了实际值
    """
    # 创建一个 Jinja2 模板环境（Environment）
    # Environment 是 Jinja2 的核心类，控制模板的各种行为
    #
    # loader=BaseLoader()：
    #   - loader 决定"从哪里加载模板"
    #   - BaseLoader() 是最简单的加载器，不从文件系统加载
    #   - 因为我们直接用字符串创建模板（env.from_string），所以不需要文件加载器
    #
    # undefined=Undefined：
    #   - undefined 决定"模板中引用了不存在的变量时怎么处理"
    #   - Undefined 策略：不报错，把未定义的变量当作空字符串处理
    #   - 这是最宽松的策略，避免因为缺少某个变量导致整个测试失败
    env = Environment(loader=BaseLoader(), undefined=Undefined)

    # 从字符串创建模板对象
    # env.from_string() 把普通字符串解析为 Jinja2 模板
    # 模板中的 {{ }} 语法会被识别为变量占位符
    template = env.from_string(template_str)

    # 渲染模板，将变量值替换到占位符中
    # **variables 是 Python 的"解包"语法（unpacking）
    # 它把字典 {"name": "张三", "age": 25} 解包为关键字参数 name="张三", age=25
    # 这样 Jinja2 就能用这些参数来替换模板中的 {{ name }} 和 {{ age }}
    rendered = template.render(**variables)

    # 返回渲染完成后的字符串
    return rendered


# ======================== 函数3：递归渲染复杂数据结构 ========================

def render_data(data: Any, variables: dict) -> Any:
    """
    递归渲染 dict/list/str 中所有的模板变量

    【功能说明】
    在实际测试中，HTTP 请求的各个部分（headers、body、url、query 参数等）
    都可能包含 {{ 变量名 }} 占位符。这些数据可能是字符串、字典、列表，甚至嵌套结构。
    这个函数能"递归地"处理所有类型的数据，把所有占位符都替换为实际值。

    【什么是递归？】
    递归就是函数在自己的定义中调用自己。
    比如处理字典时，每个 value 可能也是字典/列表/字符串，
    所以对每个 value 再调用 render_data 自己来处理。
    这样无论数据嵌套多少层，都能处理到。

    【参数说明】
    Args:
        data: 待渲染的数据，可以是任意类型（str/dict/list/int/float/bool/None）
        variables: 变量字典，存储所有可用的变量及其值

    【返回值说明】
    Returns:
        渲染后的数据，类型与输入保持一致
        例如输入 dict 就返回 dict，输入 str 就返回 str
    """
    # 第一种情况：数据是字符串类型
    # isinstance(data, str) 判断 data 是否是 str（字符串）类型
    # 如果是字符串，直接调用 render_template 渲染其中的 {{ }} 占位符
    if isinstance(data, str):
        # 直接渲染模板字符串，返回替换后的结果
        return render_template(data, variables)

    # 第二种情况：数据是字典类型
    # 例如 HTTP 请求的 headers：{"Authorization": "Bearer {{ token }}", "Content-Type": "application/json"}
    # 需要遍历字典的每个键值对，对每个 value 递归调用 render_data
    elif isinstance(data, dict):
        # 这里使用了"字典推导式"（dict comprehension），是 Python 的简洁语法
        # 完整写法等价于：
        #   result = {}
        #   for key, value in data.items():
        #       result[key] = render_data(value, variables)
        #   return result
        # 字典推导式把上面四行代码压缩成了一行，更加简洁
        # 注意：key（键）保持不变，只对 value（值）进行递归渲染
        return {key: render_data(value, variables) for key, value in data.items()}

    # 第三种情况：数据是列表类型
    # 例如一组请求参数：["{{ name }}", "{{ age }}", 123]
    # 需要对列表中的每个元素递归调用 render_data
    elif isinstance(data, list):
        # 这里使用了"列表推导式"（list comprehension），也是 Python 的简洁语法
        # 完整写法等价于：
        #   result = []
        #   for item in data:
        #       result.append(render_data(item, variables))
        #   return result
        # 列表推导式把循环和追加操作压缩成了一行
        return [render_data(item, variables) for item in data]

    # 第四种情况：其他类型（int、float、bool、None 等）
    # 这些类型不包含 {{ }} 占位符，不需要渲染，直接原样返回
    # 例如数字 200、布尔值 True、空值 None 都不需要处理
    else:
        # 原样返回，不做任何处理
        return data


# ======================== 函数4：合并数据驱动参数 ========================

def merge_data_params(test_case_dict: dict, data_params: dict) -> dict:
    """
    将数据驱动的参数合并到用例变量中

    【功能说明】
    在"数据驱动测试"中，我们会准备多组测试数据（data_params），
    每组数据代表一种测试场景。这个函数的作用就是把每组数据合并到
    用例已有的变量池中，让模板渲染时能用到这组数据。

    【优先级说明】
    data_params 的优先级高于 test_case_dict（全局变量）。
    也就是说，如果两个字典中有同名的变量（key 相同），
    data_params 中的值会覆盖 test_case_dict 中的值。
    这样做是因为"具体的测试数据"应该比"全局默认值"更重要。

    【参数说明】
    Args:
        test_case_dict: 用例的全局变量字典
            例如：{"host": "api.example.com", "token": "global_token"}
        data_params: 数据驱动的参数字典（优先级更高）
            例如：{"token": "special_token", "user": "test_user"}

    【返回值说明】
    Returns:
        合并后的变量字典
        例如：{"host": "api.example.com", "token": "special_token", "user": "test_user"}
        注意 token 被 data_params 中的值覆盖了
    """
    # 第一步：复制全局变量字典
    # .copy() 方法创建字典的"浅拷贝"（shallow copy）
    # 为什么要复制？因为不想修改原始的全局变量字典
    # 如果不复制直接 update，会改变原始字典，影响到后续其他测试用例
    merged = test_case_dict.copy()

    # 第二步：用 data_params 中的键值对覆盖 merged 中的同名键
    # .update() 方法会把一个字典的所有键值对添加到另一个字典中
    # 如果有同名键，新字典的值会覆盖旧字典的值
    # 例如：merged = {"a": 1, "b": 2}，data_params = {"b": 3, "c": 4}
    #       merged.update(data_params) 后 merged = {"a": 1, "b": 3, "c": 4}
    merged.update(data_params)

    # 返回合并后的字典
    return merged
