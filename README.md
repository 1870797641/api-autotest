# 接口自动化测试框架

> 一个用 YAML 写测试用例的接口自动化测试工具，不用写代码，测试人员也能上手。

## 这个框架能干什么？

简单说，就是帮你**自动调接口、自动判断结果对不对**。

以前测接口，你得自己打开 Postman 或者写 Python 脚本，一个个调、一个个看返回值。这个框架让你：

1. 在一个 YAML 文件里写好要测哪些接口
2. 运行一条命令，所有接口按顺序自动跑完
3. 自动生成一份漂亮的 HTML 报告，哪些过了、哪些挂了一目了然

### 核心能力

- **YAML 写用例** — 不用写代码，写配置就行，测试人员也能上手
- **接口编排** — 接口之间有依赖关系？比如"先登录拿到 token，再用 token 调其他接口"，框架自动帮你按顺序执行
- **数据驱动** — 同一个接口想用不同的参数测多遍？写一个用例，配上多组数据就行
- **多环境切换** — 开发环境、测试环境、生产环境，改一行配置就切换
- **自动生成报告** — 跑完自动出 HTML 报告，打开浏览器就能看
- **自动重试** — 网络抖了一下？框架会自动重试，不会因为一次失败就挂掉
- **丰富断言** — 支持检查状态码、返回值、响应时间、正则匹配

---

## 环境准备

你需要：

- **Python 3.8 或更高版本**
- **pip**（Python 自带的包管理工具）

### 第一步：下载代码

```bash
git clone https://github.com/1870797641/api-autotest-.git
cd api-autotest-
```

### 第二步：安装依赖

```bash
pip install -r requirements.txt
```

装完就 4 个包：`requests`（发 HTTP 请求）、`PyYAML`（解析 YAML）、`Jinja2`（模板引擎）、`jsonpath-ng`（从 JSON 里取值）。

---

## 快速上手

### 最简单的用法

```bash
python main.py
```

运行后会做以下事情：
1. 读取 `testcases/demo_api.yaml` 里的测试用例
2. 使用 `config/environments/dev.yaml` 的配置（默认开发环境）
3. 自动执行所有接口测试
4. 在 `reports/` 目录生成一份 HTML 报告

### 指定环境和用例

```bash
# 用测试环境跑
python main.py --env test

# 用生产环境跑
python main.py --env prod

# 指定用例文件
python main.py --cases testcases/demo_api.yaml

# 用测试环境 + 指定用例文件，一起用
python main.py --env test --cases testcases/demo_api.yaml
```

### 其他选项

```bash
# 开启详细日志（调试用）
python main.py --env dev --log-level DEBUG

# 不生成报告（只看控制台输出）
python main.py --env prod --no-report

# 报告输出到别的目录
python main.py --report-dir my_reports
```

### 命令行参数一览

| 参数 | 可选值 | 默认值 | 说明 |
|------|--------|--------|------|
| `--env` | `dev` / `test` / `prod` | `dev` | 用哪个环境的配置 |
| `--cases` | 文件路径 | `testcases/demo_api.yaml` | 测试用例文件 |
| `--report-dir` | 目录路径 | `reports` | 报告放哪里 |
| `--log-level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | `INFO` | 日志详细程度 |
| `--no-report` | 加了就不生成 | 生成报告 | 跳过报告生成 |

---

## 怎么写测试用例？

测试用例就是 YAML 文件，格式很简单。下面从零教你写。

### 基本结构

```yaml
testcases:
  - id: 接口名          # 用例唯一标识，不能重复
    name: 接口名称       # 用例名称，显示在报告里
    method: GET          # HTTP 方法：GET / POST / PUT / DELETE / PATCH
    url: http://xxx      # 接口地址
    headers:             # 请求头（可选）
      Content-Type: application/json
    body:                # 请求体（可选，POST/PUT 用）
      key: value
    assertions:          # 断言规则（可选）
      - type: status_code
        expected: 200
```

### 示例1：最简单的 GET 请求

```yaml
testcases:
  - id: health_check
    name: "健康检查接口"
    method: GET
    url: "http://localhost:8080/api/health"
    assertions:
      - type: status_code
        expected: 200
```

这就是一个最简单的用例：调一个 GET 接口，检查状态码是不是 200。

### 示例2：POST 请求 + 检查返回值

```yaml
testcases:
  - id: user_login
    name: "用户登录"
    method: POST
    url: "http://localhost:8080/api/auth/login"
    headers:
      Content-Type: "application/json"
    body:
      username: "admin"
      password: "admin123"
    assertions:
      # 检查状态码是 200
      - type: status_code
        expected: 200
      # 检查返回的 JSON 里有 token 字段
      - type: jsonpath
        path: "$.data.token"
        operator: exists
        expected: true
```

### 示例3：接口之间有依赖

比如你想测"登录 → 获取用户信息 → 删除用户"，后面的操作依赖前面的结果。

```yaml
testcases:
  # 第一步：登录，提取 token
  - id: login
    name: "用户登录"
    method: POST
    url: "http://localhost:8080/api/auth/login"
    headers:
      Content-Type: "application/json"
    body:
      username: "admin"
      password: "admin123"
    assertions:
      - type: status_code
        expected: 200
    extract:
      # 从返回值里提取 token，后面用 {{ token }} 引用
      token: "$.data.token"
      user_id: "$.data.user_id"

  # 第二步：用 token 获取用户信息
  - id: get_user
    name: "获取用户信息"
    depends_on: [login]          # 声明依赖 login 用例
    method: GET
    url: "http://localhost:8080/api/users/{{ user_id }}"   # 用前面提取的 user_id
    headers:
      Authorization: "Bearer {{ token }}"                  # 用前面提取的 token
    assertions:
      - type: status_code
        expected: 200
      - type: jsonpath
        path: "$.data.username"
        operator: equals
        expected: "admin"

  # 第三步：删除用户
  - id: delete_user
    name: "删除用户"
    depends_on: [get_user]
    method: DELETE
    url: "http://localhost:8080/api/users/{{ user_id }}"
    headers:
      Authorization: "Bearer {{ token }}"
    assertions:
      - type: status_code
        expected: 200
```

关键点：
- `extract` 从响应里提取变量，存到变量池
- `depends_on` 声明依赖关系，框架会自动按顺序执行
- `{{ 变量名 }}` 在 URL、headers、body 里引用前面提取的变量

### 示例4：数据驱动（同一个接口测多组数据）

```yaml
testcases:
  - id: create_user
    name: "创建用户"
    method: POST
    url: "http://localhost:8080/api/users"
    headers:
      Content-Type: "application/json"
    body:
      username: "{{ username }}"
      email: "{{ email }}"
      role: "{{ role }}"
    data_driven:
      # 每组数据执行一次，共执行 3 次
      - { username: "alice", email: "alice@example.com", role: "user" }
      - { username: "bob", email: "bob@example.com", role: "admin" }
      - { username: "charlie", email: "charlie@example.com", role: "user" }
    assertions:
      - type: status_code
        operator: in
        expected: [200, 201]
```

### 示例5：跳过某个用例

```yaml
testcases:
  - id: login
    name: "登录"
    method: POST
    url: "http://localhost:8080/api/login"
    skip: true     # 加上 skip: true，这个用例就不会执行
    body:
      username: admin
      password: 123456
```

### 示例6：套件级变量

你可以在 YAML 文件顶部定义套件级别的变量，所有用例都能用：

```yaml
test_suite:
  name: "用户管理测试"
  variables:
    base_api: "http://localhost:8080/api"

testcases:
  - id: get_user
    name: "获取用户"
    method: GET
    url: "{{ base_api }}/users/1"
    assertions:
      - type: status_code
        expected: 200
```

### 完整的 YAML 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `id` | 字符串 | **是** | 用例唯一标识，不能重复 |
| `name` | 字符串 | **是** | 用例名称，报告显示 |
| `method` | 字符串 | **是** | GET / POST / PUT / DELETE / PATCH |
| `url` | 字符串 | **是** | 请求地址，支持 `{{ 变量名 }}` |
| `headers` | 字典 | 否 | 请求头，支持模板变量 |
| `body` | 字典/字符串 | 否 | 请求体（JSON 对象或原始字符串） |
| `query_params` | 字典 | 否 | URL 查询参数 |
| `assertions` | 列表 | 否 | 断言规则列表 |
| `extract` | 字典 | 否 | 变量提取规则 |
| `depends_on` | 列表 | 否 | 依赖的前置用例 ID |
| `data_driven` | 列表 | 否 | 参数化数据列表 |
| `timeout` | 浮点数 | 否 | 单个用例超时（秒） |
| `skip` | 布尔 | 否 | 设为 true 跳过该用例 |

---

## 断言怎么写？

断言就是"验证返回结果对不对"。框架支持 4 种断言方式。

### 1. 状态码断言

检查 HTTP 返回的状态码。

```yaml
assertions:
  - type: status_code
    expected: 200                          # 默认 operator 是 equals
  - type: status_code
    operator: in                           # 状态码在列表中
    expected: [200, 201, 202]
```

### 2. JSONPath 断言

用 JSONPath 从返回的 JSON 里取值，然后比较。

```yaml
assertions:
  # 检查某个字段等于某个值
  - type: jsonpath
    path: "$.data.username"
    operator: equals
    expected: "admin"

  # 检查某个字段是否存在
  - type: jsonpath
    path: "$.data.token"
    operator: exists
    expected: true

  # 检查列表长度大于 0
  - type: jsonpath
    path: "$.data.list"
    operator: gt
    expected: 0

  # 检查字符串包含
  - type: jsonpath
    path: "$.message"
    operator: contains
    expected: "成功"

  # 检查值在列表中
  - type: jsonpath
    path: "$.data.role"
    operator: in
    expected: ["admin", "user", "guest"]
```

### 3. 响应时间断言

检查接口响应速度。

```yaml
assertions:
  - type: response_time
    operator: lt             # 小于（Less Than）
    expected: 2.0            # 响应时间要小于 2 秒
```

### 4. 正则断言

用正则表达式匹配返回内容。

```yaml
assertions:
  # 检查邮箱格式
  - type: regex
    path: "$.data.email"
    expected: "\\w+@\\w+\\.\\w+"

  # 不指定 path，对整个响应体做正则匹配
  - type: regex
    expected: "success"
```

### 操作符一览

| 操作符 | 含义 | 适用断言类型 |
|--------|------|-------------|
| `equals` | 等于（默认） | 全部 |
| `not_equals` | 不等于 | 全部 |
| `contains` | 包含 | jsonpath / regex |
| `exists` | 字段存在 | jsonpath |
| `gt` | 大于 | response_time / jsonpath |
| `lt` | 小于 | response_time / jsonpath |
| `in` | 在列表中 | status_code / jsonpath |
| `regex_match` | 正则匹配 | jsonpath |

---

## 环境配置

配置文件在 `config/environments/` 目录下，每个环境一个 YAML 文件。

### 默认的三个环境

**dev.yaml（开发环境）**
```yaml
base_url: "http://localhost:8080"
timeout: 10
verify_ssl: false
headers:
  Content-Type: "application/json"
variables:
  env_name: "dev"
```

**test.yaml（测试环境）**
```yaml
base_url: "http://test-api.example.com"
timeout: 30
verify_ssl: true
headers:
  Content-Type: "application/json"
variables:
  env_name: "test"
```

### 配置字段说明

| 字段 | 说明 |
|------|------|
| `base_url` | 接口基础地址，用例里用 `{{ base_url }}` 引用 |
| `timeout` | 全局请求超时时间（秒），用例可以单独覆盖 |
| `verify_ssl` | 是否验证 SSL 证书 |
| `headers` | 全局默认请求头，用例级 headers 会合并覆盖 |
| `variables` | 自定义变量，用例里用 `{{ 变量名 }}` 引用 |

### 怎么新增环境？

1. 在 `config/environments/` 下新建一个 YAML 文件，比如 `staging.yaml`
2. 写好配置内容
3. 运行时指定：`python main.py --env staging`

---

## 测试报告长什么样？

跑完测试后，`reports/` 目录下会生成一个 HTML 文件，用浏览器打开就行。

报告包含：
- **统计摘要**：总用例数、通过数、失败数、通过率
- **通过率进度条**：直观显示测试结果
- **用例详情表格**：每个用例的执行结果、状态码、响应时间
- **展开详情**：点击可以查看请求信息、响应信息、断言详情
- **失败用例高亮**：红色底色，一眼找到问题

---

## 项目结构

```
api-autotest-
├── config/
│   └── environments/         # 环境配置文件
│       ├── dev.yaml
│       ├── test.yaml
│       └── prod.yaml
├── framework/                 # 框架核心代码
│   ├── __init__.py
│   ├── engine.py              # 测试执行引擎（核心）
│   ├── models.py              # 数据模型定义
│   ├── assertions.py          # 断言验证引擎
│   ├── extractor.py           # 变量提取 + 模板渲染
│   ├── config_loader.py       # 配置加载器
│   └── report.py              # HTML 报告生成
├── templates/
│   └── report.html            # 报告模板
├── testcases/                 # 测试用例文件
│   └── demo_api.yaml
├── reports/                   # 生成的报告（运行时自动创建）
├── main.py                    # 命令行入口
├── requirements.txt           # Python 依赖
└── README.md
```

---

## 常见问题

### Q: 运行时报 "环境配置文件不存在"

检查 `--env` 参数的值是否正确，确保 `config/environments/` 下有对应的 YAML 文件。

### Q: 接口之间怎么传递数据？

用 `extract` 提取变量，用 `depends_on` 声明依赖。比如登录接口提取 token，后续接口用 `{{ token }}` 引用。

### Q: 怎么添加新的断言类型？

在 `framework/assertions.py` 中添加新的处理函数，注册到 `handlers` 字典即可。

### Q: 怎么集成到 CI/CD？

框架支持命令行调用，退出码 `0` 表示全部通过，`1` 表示有失败。可以轻松集成到 GitHub Actions、Jenkins 等平台。

**GitHub Actions 示例：**
```yaml
name: API Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python main.py --env test
```

---

## 依赖说明

| 包名 | 用途 |
|------|------|
| `requests` | 发送 HTTP 请求 |
| `PyYAML` | 解析 YAML 配置和用例文件 |
| `Jinja2` | 模板渲染（变量替换 + 报告模板） |
| `jsonpath-ng` | 从 JSON 响应中提取值 |

---

## License

MIT License
