"""
=============================================================================
接口自动化测试框架 - HTML 报告生成模块（report.py）
=============================================================================

【模块整体说明】
这个模块的作用是：把测试执行完之后的结果，生成一个漂亮的 HTML 网页报告。
你可以把它理解为一个"成绩单生成器"——测试跑完了，它把"成绩"整理成一份好看的报告。

具体来说，它做了以下几件事：
1. 统计数据：一共跑了多少个用例，通过了几个，失败了几个，通过率是多少
2. 准备模板数据：把统计好的数据打包，交给 Jinja2 模板引擎
3. 渲染 HTML：用 Jinja2 模板引擎把数据填入 HTML 模板文件中（templates/report.html）
4. 写入文件：把渲染好的 HTML 内容保存为一个 .html 文件，用浏览器就能打开看

【用到的技术】
- Jinja2：一个 Python 的模板引擎，类似于"填空题"，把变量填入模板中
- os 模块：处理文件路径、创建目录等操作系统相关的事情
- json 模块：把 Python 的字典/列表转换成 JSON 格式的字符串，方便展示
- datetime 模块：获取当前时间，用于给报告文件命名和显示生成时间

【在框架中的位置】
main.py → 调用 engine.run() 执行测试 → 调用本模块的 generate_report() 生成报告
=============================================================================
"""

# ---------- 导入标准库 ----------
import os       # os 模块：提供文件路径操作、目录创建等功能
import json     # json 模块：提供 JSON 数据的序列化和反序列化功能
from datetime import datetime  # datetime 类：获取当前日期和时间
from typing import Any         # Any 类型提示：表示可以是任意类型

# ---------- 导入第三方库 ----------
# Jinja2 是一个模板引擎库
# Environment：Jinja2 的运行环境，负责管理模板的加载和渲染
# FileSystemLoader：从文件系统（即磁盘上的文件夹）加载模板文件
from jinja2 import Environment, FileSystemLoader  # 导入 Jinja2 的环境类和文件加载器

# ---------- 导入框架内部模块 ----------
# ExecutionContext：执行上下文，包含了所有测试结果和执行过程中的变量
# TestResult：单个测试用例的执行结果
from framework.models import ExecutionContext, TestResult  # 导入框架内部的数据模型类


# =============================================================================
# 【常量定义】模板目录路径
# =============================================================================
# 这行代码的目的是找到 templates/ 文件夹的绝对路径。
# 拆解过程（从内到外）：
#   1. __file__           → 当前文件的路径，比如 /project/framework/report.py
#   2. os.path.abspath()  → 确保是绝对路径
#   3. os.path.dirname()  → 去掉文件名，得到 /project/framework/
#   4. os.path.dirname()  → 再上一层，得到 /project/
#   5. os.path.join(..., "templates") → 拼接得到 /project/templates/
# 为什么要这样做？因为模板文件 report.html 放在 templates/ 目录下，
# 我们需要告诉 Jinja2 去哪里找模板文件。
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")  # 获取模板目录的绝对路径


# =============================================================================
# 【辅助函数】格式化时间
# =============================================================================
def _format_time(seconds: float) -> str:  # 辅助函数：将秒数转换为可读的时间格式
    """
    将秒数转换为人类更容易阅读的时间格式。

    【为什么要这个函数？】
    测试中记录的时间都是以"秒"为单位的浮点数（比如 0.456 秒），
    但直接显示 "0.456s" 不够直观。如果时间很短，显示毫秒（ms）更好；
    如果时间较长，显示秒（s）就够了。

    【参数说明】
    seconds: float 类型，表示秒数。比如 0.123 表示 0.123 秒

    【返回值】
    str 类型的可读时间字符串：
    - 如果小于 1 秒，转成毫秒显示，比如 "456ms"
    - 如果大于等于 1 秒，保留两位小数显示，比如 "1.23s"

    【Python 语法解释】
    - f"{...}" 叫做 f-string（格式化字符串），Python 3.6+ 的语法，
      可以在字符串中直接嵌入变量和表达式
    - int(seconds * 1000) 把秒转毫秒，int() 去掉小数部分
    - :.2f 表示保留 2 位小数（f 表示浮点数格式）
    """
    # 判断：如果时间不到 1 秒，就转换为毫秒显示
    if seconds < 1:  # 判断时间是否小于 1 秒
        # seconds * 1000 把秒变成毫秒，int() 取整数部分
        # 比如 0.456 → 456，然后拼接 "ms" 变成 "456ms"
        return f"{int(seconds * 1000)}ms"  # 返回毫秒格式的时间字符串
    # 如果大于等于 1 秒，直接保留两位小数显示
    # 比如 2.3456 → "2.35s"
    return f"{seconds:.2f}s"  # 返回秒格式的时间字符串


# =============================================================================
# 【辅助函数】格式化 JSON 数据
# =============================================================================
def _format_json(data: Any) -> str:  # 辅助函数：将数据格式化为 JSON 字符串
    """
    把 Python 数据转换成好看的 JSON 字符串，用于在 HTML 报告中展示。

    【为什么要这个函数？】
    测试的请求体和响应体可能是字典（dict）、列表（list）、字符串（str）等不同类型。
    在 HTML 报告中，我们希望它们以整齐的 JSON 格式显示，所以需要统一处理。

    【参数说明】
    data: Any 类型，表示可以是任意类型的数据（字典、列表、字符串、None 等）

    【返回值】
    str 类型的格式化字符串

    【Python 语法解释】
    - isinstance(data, str)：判断 data 是不是字符串类型
    - json.dumps()：把 Python 对象转换成 JSON 字符串
      - ensure_ascii=False：允许显示中文等非 ASCII 字符（不转义为 \uXXXX）
      - indent=2：缩进 2 个空格，让 JSON 看起来有层次感
    - try/except：异常处理，如果转换失败就用 str() 强行转成字符串
    """
    # 如果数据是 None（空），直接返回空字符串，不用显示
    if data is None:  # 如果数据为空
        return ""  # 返回空字符串
    # 如果数据本身就是字符串，直接返回，不需要再做 JSON 转换
    if isinstance(data, str):  # 如果数据是字符串类型
        return data  # 直接返回原字符串
    # 尝试把数据（字典、列表等）转换成格式化的 JSON 字符串
    try:  # 尝试将数据转换为 JSON 格式
        # ensure_ascii=False 保证中文正常显示，indent=2 让输出有缩进好看
        return json.dumps(data, ensure_ascii=False, indent=2)  # 返回格式化的 JSON 字符串
    except (TypeError, ValueError):  # 捕获类型错误和值错误（数据无法序列化为 JSON）
        # 如果转换失败（比如数据里有不能序列化的对象），就用 str() 兜底
        return str(data)  # 转换失败时用 str() 兜底


# =============================================================================
# 【核心函数】生成 HTML 报告
# =============================================================================
def generate_report(context: ExecutionContext, output_dir: str = "reports") -> str:  # 核心函数：根据测试结果生成 HTML 报告
    """
    根据测试执行结果，生成一份 HTML 格式的测试报告。

    【这个函数做了什么？（完整流程）】
    1. 从 context（执行上下文）中取出所有测试结果
    2. 统计通过/失败/跳过的数量和通过率
    3. 准备模板需要的数据（字典形式）
    4. 用 Jinja2 把数据填入 HTML 模板（templates/report.html）
    5. 把渲染好的 HTML 保存到文件中
    6. 返回生成的文件路径

    【参数说明】
    context: ExecutionContext 对象，包含了所有测试结果（results 列表）和环境配置
    output_dir: 报告文件要保存到哪个目录，默认是 "reports" 文件夹

    【返回值】
    str 类型，生成的报告文件的完整路径，比如 "reports/report_20250101_120000.html"

    【设计思路】
    这个函数遵循"数据准备 → 模板渲染 → 文件输出"的三步流程，
    和 web 开发中的 MVC 模式类似：数据（Model）和展示（View/模板）是分离的。
    """
    # ---- 第一步：从上下文中取出所有测试结果列表 ----
    # context.results 是一个列表，每个元素是一个 TestResult 对象
    results = context.results  # 获取所有测试结果列表

    # ---- 第二步：统计数据 ----
    # 总共有多少个测试结果
    total = len(results)  # 计算测试用例总数
    # 统计通过的用例数量：遍历 results，计算 passed 为 True 的个数
    # sum(1 for r in results if r.passed) 是 Python 的生成器表达式写法，
    # 等价于：先创建一个列表 [1, 1, 0, 1, ...]，然后求和
    passed = sum(1 for r in results if r.passed)  # 统计通过的用例数量
    # 统计失败的用例数量：没有通过，并且有 error 信息
    # 注意：跳过的用例也有 error（比如"依赖用例失败"），但不算真正的"失败"
    failed = sum(1 for r in results if not r.passed and r.error)  # 统计失败的用例数量
    # 跳过的用例数量 = 总数 - 通过 - 失败（剩余的就算跳过）
    skipped = total - passed - failed  # 计算跳过的用例数量
    # 计算通过率（百分比），如果 total 为 0 则通过率为 0，避免除零错误
    # 这里用了 Python 的条件表达式：A if 条件 else B
    pass_rate = (passed / total * 100) if total > 0 else 0.0  # 计算通过率（百分比）
    # 计算所有用例的总响应时间（把每个用例的 response_time 加起来）
    total_time = sum(r.response_time for r in results)  # 累加所有用例的响应时间

    # ---- 第三步：获取环境名称 ----
    # 从环境配置字典中取出环境名称，优先用 "env_name"，其次用 "name"
    # dict.get(key, default) 方法：如果 key 不存在，返回 default 值
    # 这里嵌套了两层 get：先找 "env_name"，找不到就找 "name"，还找不到就返回 "未知环境"
    env_name = context.env_config.get("env_name", context.env_config.get("name", "未知环境"))  # 获取环境名称

    # ---- 第四步：获取报告的生成时间 ----
    # datetime.now() 获取当前时间，strftime() 格式化为指定的字符串格式
    # %Y=四位年份, %m=两位月份, %d=两位日期, %H=两位小时, %M=两位分钟, %S=两位秒数
    # 比如："2025-01-01 12:00:00"
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 获取当前时间并格式化为字符串

    # ---- 第五步：准备模板数据 ----
    # 把所有需要传给 HTML 模板的数据打包成一个字典（dict）
    # Jinja2 模板中可以用 {{ 变量名 }} 来引用这些数据
    template_context = {  # 构建传给 Jinja2 模板的数据字典
        "title": "接口自动化测试报告",        # 报告的标题
        "env_name": env_name,                 # 环境名称（dev/test/prod）
        "generated_at": generated_at,         # 报告生成时间
        "total": total,                       # 用例总数
        "passed": passed,                     # 通过的用例数
        "failed": failed,                     # 失败的用例数
        "skipped": skipped,                   # 跳过的用例数
        "pass_rate": round(pass_rate, 1),     # 通过率，保留 1 位小数
        "total_time": _format_time(total_time),  # 总耗时（格式化为可读字符串）
        "results": results,                   # 所有测试结果的列表，模板中会循环展示
        # 下面两个是"工具函数"，传给模板后可以在模板中调用
        "format_time": _format_time,          # 格式化时间的函数
        "format_json": _format_json,          # 格式化 JSON 的函数
    }

    # ---- 第六步：用 Jinja2 渲染 HTML 模板 ----
    # Environment 是 Jinja2 的运行环境
    # loader=FileSystemLoader(_TEMPLATE_DIR)：告诉 Jinja2 去 _TEMPLATE_DIR 目录找模板文件
    # autoescape=True：自动转义 HTML 特殊字符（比如 < > & 等），防止 XSS 攻击
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=True)  # 创建 Jinja2 运行环境，启用自动转义
    # 加载名为 "report.html" 的模板文件（在 templates/ 目录下）
    template = env.get_template("report.html")  # 加载 HTML 模板文件
    # render() 方法把模板数据填入模板中，生成最终的 HTML 字符串
    # **template_context 是 Python 的"解包"语法，把字典的键值对展开为关键字参数
    # 等价于：template.render(title="...", env_name="...", ...)
    html_content = template.render(**template_context)  # 将数据填入模板，生成最终 HTML

    # ---- 第七步：把 HTML 内容写入文件 ----
    # os.makedirs() 创建输出目录，exist_ok=True 表示目录已存在时不报错
    os.makedirs(output_dir, exist_ok=True)  # 创建输出目录，已存在时不报错
    # 用当前时间生成一个时间戳字符串，作为文件名的一部分，避免覆盖之前的报告
    # 比如 "20250101_120000"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 生成时间戳字符串
    # 拼接文件名，比如 "report_20250101_120000.html"
    filename = f"report_{timestamp}.html"  # 拼接报告文件名
    # os.path.join() 把目录和文件名拼接成完整路径，自动处理不同操作系统的路径分隔符
    filepath = os.path.join(output_dir, filename)  # 拼接完整的文件路径

    # 以写入模式（"w"）打开文件，encoding="utf-8" 确保中文能正确保存
    # with 语句叫做"上下文管理器"，它会在代码块结束后自动关闭文件，即使发生异常也会关闭
    with open(filepath, "w", encoding="utf-8") as f:  # 以写入模式打开文件，指定 UTF-8 编码
        # 把渲染好的 HTML 字符串写入文件
        f.write(html_content)  # 将 HTML 内容写入文件

    # 返回生成的文件路径，方便外部知道报告保存到了哪里
    return filepath  # 返回生成的报告文件路径
