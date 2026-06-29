"""
================================================================================
接口自动化测试框架 - 数据模型定义模块
================================================================================

【模块整体说明】
这个文件是整个测试框架的"数据结构中心"，定义了所有核心数据的"形状"。
你可以把它理解为一组"表格模板"——每个 dataclass 就是一张表格的结构定义，
规定了这张表有哪些列、每列是什么类型、默认值是什么。

为什么要单独定义这些模型？
1. 统一管理：所有数据结构集中在一个文件里，方便查看和维护
2. 类型安全：通过类型注解（type hints），让 IDE 能自动提示和检查错误
3. 代码简洁：使用 dataclass 装饰器，自动生成 __init__、__repr__ 等方法
4. 易于序列化：这些模型可以方便地与 YAML/JSON 互相转换

【核心概念】
- dataclass: Python 3.7+ 的装饰器，自动生成初始化方法、字符串表示等
- Enum: 枚举类型，用于定义一组固定的常量值
- Optional: 表示"可以有值，也可以是 None"
- field: dataclass 的字段配置工具，用于设置默认值等

【文件结构】
1. 枚举类定义（HttpMethod, AssertionType, Operator）
2. 断言模型（Assertion）
3. 测试用例模型（TestCase）
4. 断言结果模型（AssertionResult）
5. 测试结果模型（TestResult）
6. 执行上下文模型（ExecutionContext）
================================================================================
"""

# =============================================================================
# 导入部分
# =============================================================================

# 从 dataclasses 模块导入 dataclass 装饰器和 field 函数
# - dataclass: 装饰器，自动为类生成 __init__、__repr__、__eq__ 等常用方法
# - field: 用于配置 dataclass 字段的额外参数，比如设置默认值、默认工厂函数等
from dataclasses import dataclass, field

# 从 typing 模块导入类型提示工具
# - Any: 表示"任意类型"，当类型不确定时使用
# - List: 列表类型的泛型写法，如 List[str] 表示字符串列表
# - Optional: 可选类型，Optional[str] 等价于 str | None（可以是字符串或 None）
from typing import Any, List, Optional

# 从 enum 模块导入 Enum 基类
# Enum 用于创建枚举，即一组命名的常量。比如 HTTP 方法只能是固定的几个值
from enum import Enum


# =============================================================================
# 枚举类定义 - 定义固定的常量集合
# =============================================================================

class HttpMethod(Enum):
    """
    HTTP 请求方法枚举
    
    【什么是枚举？】
    枚举是一种特殊的类，它的每个成员都是一个固定不变的常量。
    使用枚举的好处：
    1. 避免拼写错误（比如把 "GET" 写成 "get" 或 "Get"）
    2. 代码更清晰（HttpMethod.GET 比 "GET" 更有语义）
    3. IDE 可以自动补全所有可用的方法
    
    【语法说明】
    - 继承 Enum 后，每个类属性都会成为枚举成员
    - 等号左边是枚举成员名（代码中引用的名字）
    - 等号右边是枚举成员的值（实际使用的字符串）
    
    【业务含义】
    HTTP 协议定义了多种请求方法，每种方法代表不同的操作意图：
    - GET: 获取资源（查询数据）
    - POST: 创建资源（提交新数据）
    - PUT: 完整更新资源（替换整个资源）
    - DELETE: 删除资源
    - PATCH: 部分更新资源（只修改某些字段）
    - HEAD: 获取资源头信息（不返回响应体）
    - OPTIONS: 查询服务器支持的方法
    """
    GET = "GET"         # 获取资源，最常用的请求方法
    POST = "POST"       # 创建新资源，通常带有请求体
    PUT = "PUT"         # 完整替换资源
    DELETE = "DELETE"   # 删除资源
    PATCH = "PATCH"     # 部分更新资源
    HEAD = "HEAD"       # 仅获取响应头，不获取响应体
    OPTIONS = "OPTIONS" # 查询服务器支持的 HTTP 方法


class AssertionType(Enum):
    """
    断言类型枚举
    
    【什么是断言？】
    断言（Assertion）就是"验证"的意思——检查接口的实际响应是否符合预期。
    比如：预期状态码是 200，实际返回也是 200，则断言通过。
    
    【业务含义】
    框架支持多种断言方式，每种方式从不同角度验证响应：
    """
    # 状态码断言：验证 HTTP 响应状态码，如 200、404、500 等
    # 这是最基础的断言，几乎每个测试用例都会检查状态码
    STATUS_CODE = "status_code"
    
    # JSONPath 值断言：使用 JSONPath 表达式从 JSON 响应体中提取特定值，然后验证
    # 比如 $.data.name 可以提取 {"data": {"name": "张三"}} 中的 "张三"
    JSONPATH = "jsonpath"
    
    # 响应时间断言：验证接口响应耗时是否在可接受范围内
    # 比如要求某个接口必须在 500ms 内返回
    RESPONSE_TIME = "response_time"
    
    # 正则表达式断言：使用正则表达式匹配响应内容
    # 适用于验证格式，比如邮箱格式、手机号格式等
    REGEX = "regex"


class Operator(Enum):
    """
    断言操作符枚举
    
    【业务含义】
    操作符定义了"如何比较"期望值和实际值。
    比如：是判断"相等"，还是判断"包含"，还是判断"大于"？
    """
    # 等于：实际值必须与期望值完全相等
    # 例：期望 200，实际也必须是 200
    EQUALS = "equals"
    
    # 包含：实际值必须包含期望值（用于字符串或列表）
    # 例：期望 "success"，实际 "operation success" 也算通过
    CONTAINS = "contains"
    
    # 存在：只检查某个字段是否存在，不关心具体值
    # 例：检查响应中是否有 "token" 字段
    EXISTS = "exists"
    
    # 大于（Greater Than）：实际值必须大于期望值
    # 例：期望列表长度 > 0
    GT = "gt"
    
    # 小于（Less Than）：实际值必须小于期望值
    # 例：期望响应时间 < 500ms
    LT = "lt"
    
    # 在列表中：实际值必须在指定的列表范围内
    # 例：期望状态码 in [200, 201, 202]
    IN = "in"
    
    # 正则匹配：实际值必须匹配指定的正则表达式
    # 例：期望邮箱格式符合 \w+@\w+\.\w+
    REGEX_MATCH = "regex_match"


# =============================================================================
# 数据模型定义 - 使用 dataclass 定义核心数据结构
# =============================================================================

@dataclass
class Assertion:
    """
    断言模型
    
    【什么是 dataclass？】
    @dataclass 是 Python 的装饰器，它会自动为这个类生成：
    1. __init__ 方法：初始化方法，根据字段定义自动生成
    2. __repr__ 方法：字符串表示，打印对象时显示友好信息
    3. __eq__ 方法：相等比较，可以比较两个对象是否相同
    
    【使用方式】
    创建对象时不需要写 __init__，直接按字段顺序传参：
    assertion = Assertion(type="status_code", operator="equals", expected=200)
    
    【业务含义】
    一条断言规则 = 断言类型 + 操作符 + 期望值 + （可选的提取路径）
    比如："验证状态码等于 200" 就是一条断言规则
    """
    
    # 断言类型：指定使用哪种断言方式
    # 取值范围：status_code / jsonpath / response_time / regex
    # 这是必填字段（没有默认值），创建对象时必须提供
    type: str
    
    # JSONPath 路径：用于从 JSON 响应体中提取特定值
    # 只有当 type 为 "jsonpath" 时才需要这个字段
    # Optional[str] 表示可以是字符串，也可以是 None
    # 默认值为 None，即不设置此字段时自动为 None
    path: Optional[str] = None
    
    # 操作符：指定如何比较期望值和实际值
    # 默认值为 "equals"（等于），即如果不指定操作符，默认判断相等
    operator: str = "equals"
    
    # 期望值：断言时期望得到的值
    # Any 类型表示可以是任意类型：数字、字符串、列表、字典等
    # 比如：200（数字）、"success"（字符串）、[200, 201]（列表）
    # 默认值为 None
    expected: Any = None


@dataclass
class TestCase:
    """
    测试用例模型
    
    【业务含义】
    这是整个框架最核心的数据结构，代表一个完整的接口测试用例。
    一个测试用例包含：
    1. 基本信息：ID、名称
    2. 请求信息：方法、URL、请求头、请求体、查询参数
    3. 验证规则：断言列表
    4. 高级特性：变量提取、依赖关系、数据驱动、超时设置
    
    【YAML 中的样子】
    在 YAML 文件中，一个测试用例大概长这样：
    - id: get_user
      name: 获取用户信息
      method: GET
      url: "{{base_url}}/api/users/1"
      assertions:
        - type: status_code
          operator: equals
          expected: 200
    """
    
    # ========== 基本信息 ==========
    
    # 用例唯一标识（ID）
    # 在整个测试文件中必须唯一，用于：
    # 1. 其他用例通过 depends_on 引用它
    # 2. 从它的响应中提取变量（如 extract）
    # 3. 测试报告中标识具体哪个用例失败
    # 示例："login_success", "get_user_list"
    id: str
    
    # 用例名称：人类可读的描述性名称
    # 主要用于测试报告和日志输出，方便理解用例的目的
    # 示例："登录成功-正常用户", "获取用户列表-第一页"
    name: str
    
    # ========== 请求信息 ==========
    
    # HTTP 请求方法
    # 决定请求的类型：GET（查询）、POST（创建）、PUT（更新）、DELETE（删除）等
    # 支持 Jinja2 模板变量，比如可以写成 "{{method}}" 然后从变量中获取
    method: str
    
    # 请求 URL：接口地址
    # 支持 Jinja2 模板变量，这是非常强大的特性：
    # - {{base_url}}/api/users  可以根据环境自动替换为不同的域名
    # - {{base_url}}/api/users/{{user_id}}  可以动态替换路径参数
    url: str
    
    # 请求头（HTTP Headers）：以字典形式存储
    # 字典是 Python 中的键值对集合，类似 JSON 对象
    # 示例：{"Content-Type": "application/json", "Authorization": "Bearer xxx"}
    #
    # 【语法说明 - field(default_factory=dict)】
    # 为什么不直接写 headers: dict = {} ？
    # 因为 Python 中可变对象（如字典、列表）作为默认值会有"共享"问题：
    # 所有实例会共用同一个字典对象，修改一个会影响其他所有实例。
    # default_factory=dict 表示"每次创建新实例时，都创建一个新的空字典"
    headers: dict = field(default_factory=dict)
    
    # 请求体（HTTP Body）：发送给服务器的数据
    # Optional[Any] 表示：
    # - 可以是字典（会自动转为 JSON 发送）
    # - 可以是字符串（作为原始文本发送）
    # - 也可以是 None（GET 请求通常没有请求体）
    # 示例：{"username": "admin", "password": "123456"}
    body: Optional[Any] = None
    
    # URL 查询参数（Query Parameters）：拼接在 URL 后面的参数
    # 字典形式，key=参数名，value=参数值
    # 示例：{"page": "1", "size": "10"} 会生成 ?page=1&size=10
    # 同样使用 default_factory 避免可变默认值问题
    query_params: dict = field(default_factory=dict)
    
    # ========== 验证规则 ==========
    
    # 断言规则列表：List[Assertion] 表示这是一个 Assertion 对象的列表
    # 一个用例可以有多个断言，全部通过才算用例通过
    # 示例：
    #   - 断言1：状态码等于 200
    #   - 断言2：响应体中的 code 字段等于 0
    #   - 断言3：响应时间小于 500ms
    assertions: List[Assertion] = field(default_factory=list)
    
    # ========== 高级特性 ==========
    
    # 变量提取规则：从响应中提取值并存入全局变量池
    # 字典形式：key=变量名（后续用例中可用 {{变量名}} 引用）
    #          value=JSONPath 表达式（指定如何从响应中提取值）
    #
    # 【业务场景】
    # 比如登录接口返回 token，后续接口都需要用这个 token：
    # extract: {"token": "$.data.token"}
    # 这样后续用例就可以用 {{token}} 来引用提取到的值
    extract: dict = field(default_factory=dict)
    
    # 依赖的用例 ID 列表：指定本用例依赖哪些其他用例
    # 本用例必须在这些依赖用例都执行成功后才能运行
    #
    # 【业务场景】
    # 比如"修改用户"用例必须依赖"创建用户"用例先执行：
    # depends_on: ["create_user"]
    depends_on: List[str] = field(default_factory=list)
    
    # 参数化数据（数据驱动）：用于同一接口使用多组不同数据进行测试
    # List[dict] 表示这是一个字典列表，每个字典是一组测试参数
    # None 表示不使用数据驱动（默认值）
    #
    # 【业务场景】
    # 测试登录接口时，可以用多组账号密码：
    # data_driven:
    #   - username: "user1", password: "pass1"
    #   - username: "user2", password: "pass2"
    # 这样同一个用例会执行两次，每次用不同的参数
    data_driven: Optional[List[dict]] = None
    
    # 用例超时时间（秒）：单个用例的最大等待时间
    # Optional[float] 表示可以是浮点数（如 30.5），也可以是 None
    # None 表示使用全局配置的超时时间
    # 设置后会覆盖全局超时，适用于某些特别慢的接口
    timeout: Optional[float] = None


@dataclass
class AssertionResult:
    """
    单条断言的执行结果
    
    【业务含义】
    当一个测试用例执行完毕后，每条断言规则都会产生一个结果。
    这个模型记录：用了什么断言规则、是否通过、实际值是多少、有什么附加信息。
    
    【与 Assertion 的关系】
    Assertion 是"规则"（期望什么），AssertionResult 是"结果"（实际怎样）
    一个 Assertion 对应一个 AssertionResult
    """
    
    # 对应的断言规则：保留原始规则信息，方便在报告中展示
    # 比如：Assertion(type="status_code", operator="equals", expected=200)
    assertion: Assertion
    
    # 该断言是否通过：布尔值，True=通过，False=失败
    passed: bool
    
    # 从响应中提取的实际值
    # 用于与断言规则中的期望值（expected）进行对比
    # 比如：期望状态码 200，实际值可能是 200 或 404
    actual_value: Any
    
    # 结果描述信息：附加的文字说明
    # 通过时可以为空字符串
    # 失败时包含具体的错误说明，比如："期望 200，实际 404"
    message: str = ""


@dataclass
class TestResult:
    """
    测试用例执行结果
    
    【业务含义】
    记录一个测试用例的完整执行信息，包括：
    1. HTTP 响应数据（状态码、响应体、响应头、耗时）
    2. 所有断言的详细结果
    3. 异常信息（如果有）
    4. 数据驱动参数（如果是参数化测试）
    
    这些信息会用于生成测试报告，帮助分析测试结果。
    """
    
    # 对应的测试用例：保留原始用例信息
    test_case: TestCase
    
    # 用例整体是否通过
    # 只有当所有断言都通过时，这个值才为 True
    # 任何一个断言失败，或者请求本身出错，这个值都为 False
    passed: bool
    
    # HTTP 响应状态码：如 200、404、500 等
    # Optional[int] 表示如果请求还没发出就失败了（比如 URL 错误），这个值为 None
    status_code: Optional[int] = None
    
    # 响应体内容：服务器返回的数据
    # 如果响应是 JSON 格式，会自动解析为 Python 字典/列表
    # 否则为原始字符串
    response_body: Any = None
    
    # 响应头字典：服务器返回的 HTTP 头信息
    # 示例：{"Content-Type": "application/json", "X-Request-Id": "abc123"}
    response_headers: dict = field(default_factory=dict)
    
    # 响应耗时（秒）：从发送请求到收到完整响应的