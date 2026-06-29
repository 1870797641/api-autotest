"""
接口自动化测试框架 - 命令行入口
用法：python main.py --env dev --cases testcases/demo_api.yaml --report-dir reports
"""  # 模块文档字符串，说明框架用途和命令行用法
import argparse  # 导入命令行参数解析模块
import sys  # 导入系统模块，用于获取系统信息和退出码
import logging  # 导入日志模块

from framework.engine import TestEngine  # 导入测试引擎类
from framework.report import generate_report  # 导入报告生成函数


def parse_args():  # 定义解析命令行参数的函数
    """解析命令行参数"""  # 函数文档字符串
    parser = argparse.ArgumentParser(  # 创建参数解析器实例
        description="接口自动化测试框架 - 命令行工具",  # 设置描述信息
        formatter_class=argparse.RawDescriptionHelpFormatter,  # 使用原始格式帮助信息
        epilog=(  # 设置示例信息
            "示例:\n"
            "  python main.py --env dev --cases testcases/demo_api.yaml\n"
            "  python main.py --env prod --cases testcases/smoke.yaml --no-report\n"
            "  python main.py --env test --log-level DEBUG\n"
        ),
    )
    parser.add_argument(  # 添加环境参数
        "--env",  # 参数名称
        type=str,  # 参数类型为字符串
        default="dev",  # 默认值为"dev"
        choices=["dev", "test", "prod"],  # 可选值列表
        help="环境名称（默认: dev）",  # 帮助信息
    )
    parser.add_argument(  # 添加用例文件路径参数
        "--cases",  # 参数名称
        type=str,  # 参数类型为字符串
        default="testcases/demo_api.yaml",  # 默认用例文件路径
        help="用例文件路径（默认: testcases/demo_api.yaml）",  # 帮助信息
    )
    parser.add_argument(  # 添加报告输出目录参数
        "--report-dir",  # 参数名称
        type=str,  # 参数类型为字符串
        default="reports",  # 默认报告目录
        help="报告输出目录（默认: reports）",  # 帮助信息
    )
    parser.add_argument(  # 添加日志级别参数
        "--log-level",  # 参数名称
        type=str,  # 参数类型为字符串
        default="INFO",  # 默认日志级别
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],  # 可选日志级别
        help="日志级别（默认: INFO）",  # 帮助信息
    )
    parser.add_argument(  # 添加不生成报告参数
        "--no-report",  # 参数名称
        action="store_true",  # 设置为动作参数，存在即为True
        default=False,  # 默认值为False
        help="不生成测试报告",  # 帮助信息
    )
    return parser.parse_args()  # 解析并返回参数


def setup_logging(level_name: str):  # 定义配置日志的函数，接收日志级别名称
    """配置日志格式和级别"""  # 函数文档字符串
    level = getattr(logging, level_name.upper(), logging.INFO)  # 获取日志级别，未找到则使用INFO
    logging.basicConfig(  # 配置日志基础设置
        level=level,  # 设置日志级别
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",  # 设置日志格式
        datefmt="%Y-%m-%d %H:%M:%S",  # 设置日期时间格式
    )


def print_summary(context):  # 定义打印摘要的函数，接收测试上下文
    """打印执行摘要并返回是否有失败用例"""  # 函数文档字符串
    results = context.results  # 获取测试结果列表
    total = len(results)  # 计算总用例数
    passed = sum(1 for r in results if r.passed)  # 统计通过用例数
    failed = sum(1 for r in results if not r.passed and r.error != "依赖用例失败" and r.error != "用例已标记跳过")  # 统计失败用例数（排除依赖失败和跳过）
    skipped = total - passed - failed  # 计算跳过用例数

    logger = logging.getLogger("main")  # 获取main日志记录器
    logger.info("=" * 50)  # 打印分隔线
    logger.info("执行摘要")  # 打印摘要标题
    logger.info("=" * 50)  # 打印分隔线
    logger.info("总数: %d", total)  # 打印总用例数
    logger.info("通过: %d", passed)  # 打印通过用例数
    logger.info("失败: %d", failed)  # 打印失败用例数
    logger.info("跳过: %d", skipped)  # 打印跳过用例数
    logger.info("=" * 50)  # 打印分隔线

    return failed > 0  # 返回是否有失败用例


def main():  # 定义主函数
    args = parse_args()  # 解析命令行参数

    # 配置日志
    setup_logging(args.log_level)  # 根据参数配置日志
    logger = logging.getLogger("main")  # 获取main日志记录器

    # 打印执行信息
    logger.info("接口自动化测试框架启动")  # 记录框架启动
    logger.info("环境: %s", args.env)  # 记录当前环境
    logger.info("用例文件: %s", args.cases)  # 记录用例文件路径
    logger.info("报告目录: %s", args.report_dir)  # 记录报告输出目录
    logger.info("生成报告: %s", "否" if args.no_report else "是")  # 记录是否生成报告

    try:
        # 创建引擎并执行
        engine = TestEngine(env_name=args.env)  # 创建测试引擎实例
        context = engine.run(case_file=args.cases)  # 执行测试用例

        # 生成报告
        if not args.no_report:  # 如果需要生成报告
            report_path = generate_report(context, args.report_dir)  # 生成测试报告
            logger.info("测试报告已生成: %s", report_path)  # 记录报告路径

        # 打印摘要
        has_failures = print_summary(context)  # 打印执行摘要

        # 根据结果设置退出码
        sys.exit(1 if has_failures else 0)  # 有失败用例退出码为1，否则为0

    except FileNotFoundError as e:  # 捕获文件未找到异常
        logger.error("文件未找到: %s", e)  # 记录错误信息
        sys.exit(2)  # 文件未找到退出码为2
    except Exception as e:  # 捕获其他异常
        logger.error("执行异常: %s", e, exc_info=True)  # 记录异常信息和堆栈
        sys.exit(2)  # 其他异常退出码为2


if __name__ == "__main__":  # 判断是否为直接运行（非导入）
    main()  # 调用主函数执行程序
