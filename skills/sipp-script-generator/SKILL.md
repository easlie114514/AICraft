---
name: sipp-script-generator
description: 智能生成SIPP脚本，自动适配呼叫、注册、认证等VOIP测试场景，输出符合要求的主被叫XML文件；当用户需要配置SIP协议测试、描述呼叫场景或需要批量生成测试脚本时使用
dependency:
  python:
    - openpyxl==1.3.0
---

# SIPP脚本生成器

## 任务目标
- 本Skill用于：根据用户描述的VOIP测试场景，自动生成符合SIPP工具规范的XML脚本文件
- 能力包含：场景参数提取、主被叫脚本生成、多场景模板适配、XML格式验证、批量场景处理
- 触发条件：用户描述VOIP测试需求、呼叫流程、或需要生成SIP协议测试脚本

## 前置准备
- 无需额外依赖
- **-inf文件准备**（推荐）：如果需要从外部文件指定主被叫号码，创建CSV格式文件
  ```bash
  # 创建caller_callee.csv文件
  cat > caller_callee.csv << EOF
  1000;2000
  1001;2002
  1003;2004
  EOF
  ```
  - 第一列：主叫方号码（对应`[field0]`）
  - 第二列：被叫方号码（对应`[field1]`）
  - 使用分号分隔
  - 每行代表一个呼叫

## 操作步骤

### 输入方式

**方式一：文本描述**
- 用户直接用自然语言描述测试场景
- 智能体提取参数并生成脚本

**方式二：批量文件（推荐）**
- 支持txt和xlsx格式，包含多条SIPP模拟需求
- 调用`scripts/parse_scenarios.py`解析文件
- 智能体根据解析结果生成多对配套脚本

### 标准流程（文本描述）
1. **场景描述分析**
     - 理解用户描述的测试场景类型（基本呼叫、注册、认证等）
     - 提取关键参数：
       - 呼叫方号码/URI
       - 被叫方号码/URI
       - SIP服务器地址
       - 通话时长（如适用）
       - 是否需要认证
       - 并发数（压力测试场景）

  2. **模板选择与参数化**
     - 根据场景类型选择对应的模板：
       - 基本呼叫：`assets/templates/basic-call-uac.xml` 和 `basic-call-uas.xml`
       - 注册场景：`assets/templates/register-uac.xml`
       - 带认证呼叫：`assets/templates/auth-call-uac.xml`
     - 将提取的参数替换到模板中

  3. **脚本生成**
     - 根据模板和参数生成UAC（主叫）脚本
     - 根据模板和参数生成UAS（被叫）脚本（如需要）
     - 脚本命名规范：UAC_场景名.xml 和 UAS_场景名.xml
     - 确保主被叫脚本的交互逻辑匹配

  4. **输出文件**
     - 将生成的脚本保存为XML文件
     - 提供使用说明（如何使用sipp命令运行脚本）

### 批量流程（文件输入）
1. **文件解析**
     - 调用`scripts/parse_scenarios.py`解析场景文件
     - 支持txt和xlsx格式
     - 返回JSON格式的场景列表

2. **批量生成**
     - 遍历场景列表，为每个场景生成一对脚本
     - 脚本命名：UAC_场景名.xml 和 UAS_场景名.xml
     - 保持主被叫脚本的配套关系

3. **输出汇总**
     - 生成所有脚本文件
     - 提供场景-脚本映射表
     - 提供批量运行命令示例

- 可选分支：
  - 当 **基本呼叫场景**：使用 `basic-call` 模板生成UAC和UAS脚本
  - 当 **注册场景**：使用 `register` 模板生成UAC脚本
  - 当 **需要认证的呼叫**：使用 `auth-call` 模板生成UAC脚本
  - 当 **自定义复杂场景**：参考 `assets/examples/scenario-basic/` 示例，调整消息流程

## 资源索引
- 必要脚本：见 [scripts/parse_scenarios.py](scripts/parse_scenarios.py)（用途：解析批量场景文件，支持txt/xlsx格式，返回JSON格式的场景列表）
- 领域参考：见 [references/sipp-script-guide.md](references/sipp-script-guide.md)（何时读取：需要了解SIPP脚本语法、变量系统、常见消息格式时）
- 模板资产：
  - [assets/templates/basic-call-uac.xml](assets/templates/basic-call-uac.xml)（基本呼叫主叫脚本模板）
  - [assets/templates/basic-call-uas.xml](assets/templates/basic-call-uas.xml)（基本呼叫被叫脚本模板）
  - [assets/templates/register-uac.xml](assets/templates/register-uac.xml)（注册场景脚本模板）
  - [assets/templates/auth-call-uac.xml](assets/templates/auth-call-uac.xml)（带认证的呼叫脚本模板）
- 示例资产：
  - [assets/examples/scenario-basic/](assets/examples/scenario-basic/)（完整示例：基本呼叫场景）

## 注意事项
- 确保生成的XML格式正确，标签闭合完整
- 主被叫脚本的发送-接收逻辑必须匹配（send/recv对应）
- SDP内容中的IP地址和端口应根据实际环境调整
- 动态变量（如[call_id]、[last_From:]）是SIPP内置的，无需替换
- 输出文件应使用UTF-8编码
- **背靠背设备特性**：
  - 所有INVITE和reINVITE都会自动收到100 Trying
  - UAC脚本必须在每次INVITE后检查100 Trying（非可选）
  - UAS脚本必须在接收INVITE后立即发送100 Trying
- **CSeq自动递增**：
  - SIPP工具会自动递增CSeq值
  - 脚本中统一使用`[cseq]`，无需使用`[cseq+1]`等
- **参数说明**：
  - `[field0]`：主叫方号码，从-inf文件第一列读取
  - `[field1]`：被叫方号码，从-inf文件第二列读取
  - 推荐使用`-inf`参数从文件批量指定主被叫号码
- **脚本命名规范**：
  - UAC脚本：UAC_场景名.xml
  - UAS脚本：UAS_场景名.xml
  - 批量生成时，保持主被叫脚本的配套关系

## 使用示例

### 示例1：基本呼叫测试
**功能说明**：生成一个基本呼叫场景的主被叫脚本，测试完整的INVITE-100 Trying-180 Ringing-200 OK-ACK-BYE流程

**执行方式**：智能体根据描述提取参数并生成脚本

**关键参数**：
- 呼叫方：1000@192.168.1.100
- 被叫方：2000@192.168.1.101
- SIP服务器：192.168.1.1:5060
- 通话时长：10秒

**智能体输出**：
- 生成 `UAC_basic_call.xml`（主叫脚本）
- 生成 `UAS_basic_call.xml`（被叫脚本）
- 提供运行命令示例

**使用-inf参数批量测试**：
```bash
# 创建caller_callee.csv文件
1000;2000
1001;2002
1003;2004

# 运行UAC，从文件读取主被叫号码
sipp -sf UAC_basic_call.xml -inf caller_callee.csv 192.168.1.100 -p 5061 -d 10000 -i 192.168.1.101 -mp 6000
```

### 示例3：批量场景生成（txt文件）
**功能说明**：从txt文件解析多个场景，批量生成多对SIPP脚本

**执行方式**：
1. 智能体调用`scripts/parse_scenarios.py`解析场景文件
2. 根据解析结果为每个场景生成一对脚本
3. 输出场景-脚本映射表

**输入文件（scenarios.txt）**：
```
# 场景名;主叫;被叫;服务器;时长;场景类型
basic_call_1;1000;2000;192.168.1.100;10;basic_call
basic_call_2;1001;2001;192.168.1.100;15;basic_call
auth_call;1002;2002;192.168.1.100;10;auth_call
```

**智能体输出**：
- 解析场景文件，识别3个场景
- 生成脚本对：
  - `UAC_basic_call_1.xml` 和 `UAS_basic_call_1.xml`
  - `UAC_basic_call_2.xml` 和 `UAS_basic_call_2.xml`
  - `UAC_auth_call.xml` 和 `UAS_auth_call.xml`
- 提供场景-脚本映射表
- 提供批量运行命令示例

### 示例4：批量场景生成（xlsx文件）
**功能说明**：从xlsx文件解析多个场景，批量生成多对SIPP脚本

**输入文件（scenarios.xlsx）**：
| 场景名 | 主叫 | 被叫 | 服务器 | 时长 | 场景类型 |
|--------|------|------|--------|------|----------|
| scenario_1 | 1000 | 2000 | 192.168.1.100 | 10 | basic_call |
| scenario_2 | 1001 | 2001 | 192.168.1.100 | 20 | basic_call |

**智能体输出**：
- 解析xlsx文件，识别2个场景
- 生成脚本对：
  - `UAC_scenario_1.xml` 和 `UAS_scenario_1.xml`
  - `UAC_scenario_2.xml` 和 `UAS_scenario_2.xml`
- 提供使用说明

### 示例2：注册测试
**功能说明**：生成SIP注册脚本，测试REGISTER-401-AUTH流程

**执行方式**：智能体使用register模板生成脚本

**关键参数**：
- 注册用户：1000
- 注册域名：sip.example.com
- 认证用户名：1000
- 认证密码：password123

**智能体输出**：
- 生成 `register_uac.xml`
- 提供带认证信息的完整脚本

### 示例3：压力测试脚本
**功能说明**：生成高并发呼叫测试脚本

**执行方式**：基于basic-call模板，增加并发参数配置

**关键参数**：
- 并发数：100
- 呼叫速率：10 calls/sec
- 每轮时长：60秒
- 循环次数：100次

**智能体输出**：
- 生成 `stress_test_uac.xml`
- 提供sipp命令行参数说明（-r, -l, -m等）
