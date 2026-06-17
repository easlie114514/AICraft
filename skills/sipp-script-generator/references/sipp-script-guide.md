# SIPP脚本参考指南

## 目录
- [基础语法](#基础语法)
- [消息类型](#消息类型)
- [变量系统](#变量系统)
- [SDP格式](#sdp格式)
- [常见场景示例](#常见场景示例)

## 概览
本文档提供SIPP脚本的完整语法说明、常用消息类型定义、变量系统说明，以及常见测试场景的完整示例。用于指导智能体生成符合SIPP规范的XML脚本。

**特殊说明**：
- **背靠背设备场景**：本Skill默认针对背靠背设备，所有INVITE和reINVITE都会自动收到100 Trying
- **CSeq自动递增**：SIPP工具会自动递增CSeq值，脚本中统一使用`[cseq]`，无需使用`[cseq+1]`等

## 基础语法

### XML根结构
```xml
<?xml version="1.0" encoding="UTF-8" ?>
<scenario name="场景名称">
  <!-- 消息序列 -->
</scenario>
```

### 消息定义
SIPP脚本由一系列消息组成，每条消息可以是发送（send）或接收（recv）：

```xml
<!-- 发送消息 -->
<send>
  <![CDATA[
    消息内容
  ]]>
</send>

<!-- 接收消息 -->
<recv response="200">
</recv>
```

### 常用属性
- `name`：场景名称
- `recv response`：期望接收的响应码
- `request`：期望接收的请求方法（INVITE, BYE等）
- `optional="true"`：标记为可选消息
- `rtd`：响应时间统计
- `start_rtd`和`crlf`：计时和行结束符

## 消息类型

### INVITE（呼叫请求）
```xml
<send retrans="500">
  <![CDATA[
    INVITE sip:[service]@[remote_ip]:[remote_port] SIP/2.0
    Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
    From: [field0] <sip:[field0]@[local_ip]:[local_port]>;tag=[call_number]
    To: <sip:[service]@[remote_ip]:[remote_port]>
    Call-ID: [call_id]
    CSeq: [cseq] INVITE
    Contact: <sip:[field0]@[local_ip]:[local_port]>
    Max-Forwards: 70
    Subject: Performance Test
    Content-Type: application/sdp
    Content-Length: [len]

    v=0
    o=user1 53655765 2353687637 IN IP[local_ip_type] [local_ip]
    s=-
    c=IN IP[media_ip_type] [media_ip]
    t=0 0
    m=audio [media_port] RTP/AVP 0 8 101
    a=rtpmap:0 PCMU/8000
    a=rtpmap:8 PCMA/8000
    a=rtpmap:101 telephone-event/8000
    a=fmtp:101 0-15
  ]]>
</send>
```

### 100 Trying（尝试）
100 Trying是1xx临时响应，表示服务器已收到请求正在处理，通常由服务器立即发送。

**背靠背设备特性**：
- 背靠背设备会在收到INVITE后立即发送100 Trying
- 这是必须的响应，不是可选的
- 适用于所有INVITE和reINVITE消息

**UAC接收100 Trying（非可选）：**
```xml
<recv response="100">
</recv>
```

**UAS发送100 Trying：**
```xml
<send>
  <![CDATA[
    SIP/2.0 100 Trying
    [last_Via:]
    [last_From:]
    [last_To:];tag=[call_number]
    [last_Call-ID:]
    [last_CSeq:]
    Contact: <sip:[local_ip]:[local_port];transport=[transport]>
    Content-Length: 0
  ]]>
</send>
```

**注意事项：**
- 100 Trying是可选消息，建议使用`optional="true"`标记
- To头需要tag参数（UAS发送时）
- 不包含消息体，Content-Length为0
- 表示请求已接收，正在处理中

### 180 Ringing（振铃）
```xml
<recv response="180" rtd="true">
</recv>
```

### 200 OK（成功响应）
```xml
<recv response="200" rtd="true">
</recv>
```

### ACK（确认）
```xml
<send>
  <![CDATA[
    ACK sip:[field1]@[remote_ip]:[remote_port] SIP/2.0
    Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
    From: [field0] <sip:[field0]@[local_ip]:[local_port]>;tag=[call_number]
    To: <sip:[field1]@[remote_ip]:[remote_port]>[peer_tag_param]
    Call-ID: [call_id]
    CSeq: [cseq] ACK
    Contact: <sip:[field0]@[local_ip]:[local_port]>
    Max-Forwards: 70
    Content-Length: 0
  ]]>
</send>
```

### BYE（结束呼叫）
```xml
<send>
  <![CDATA[
    BYE sip:[field1]@[remote_ip]:[remote_port] SIP/2.0
    Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
    From: [field0] <sip:[field0]@[local_ip]:[local_port]>;tag=[call_number]
    To: <sip:[field1]@[remote_ip]:[remote_port]>[peer_tag_param]
    Call-ID: [call_id]
    CSeq: [cseq] BYE
    Max-Forwards: 70
    Content-Length: 0
  ]]>
</send>
```

### REGISTER（注册）
```xml
<send>
  <![CDATA[
    REGISTER sip:[remote_ip] SIP/2.0
    Via: SIP/2.0/[transport] [local_ip]:[local_port];branch=[branch]
    From: <sip:[field0]@[remote_ip]>;tag=[call_number]
    To: <sip:[field0]@[remote_ip]>
    Call-ID: [call_id]
    CSeq: [cseq] REGISTER
    Contact: <sip:[field0]@[local_ip]:[local_port]>
    Max-Forwards: 70
    Expires: 3600
    Content-Length: 0
  ]]>
</send>
```

## 变量系统

### 内置变量
- `[field0]`：自定义字段0，通常用于表示主叫方号码（从-inf文件第一列读取）
- `[field1]`：自定义字段1，通常用于表示被叫方号码（从-inf文件第二列读取）
- `[remote_ip]`：远程服务器IP
- `[remote_port]`：远程服务器端口
- `[local_ip]`：本地IP地址
- `[local_port]`：本地端口
- `[transport]`：传输协议（UDP/TCP/TLS）
- `[media_ip]`：媒体IP
- `[media_port]`：媒体端口
- `[call_id]`：唯一呼叫ID
- `[cseq]`：CSeq序列号
- `[call_number]`：呼叫编号
- `[branch]`：Via分支ID
- `[field2]`、`[field3]`：其他自定义字段
- `[peer_tag_param]`：对端标签参数

### -inf文件格式
使用`-inf`参数可以从外部文件读取主被叫号码等参数，格式如下：

```
1000;2000
1001;2002
1003;2004
```

- 每行代表一个呼叫
- 第一列对应`[field0]`（主叫方）
- 第二列对应`[field1]`（被叫方）
- 使用分号（;）作为分隔符
- SIPP会逐行读取，为每个呼叫使用不同号码

**使用示例**：
```bash
sipp -sf uac.xml -inf caller_callee.csv 192.168.1.100 -p 5061
```

### 变量操作
- SIPP工具会自动递增CSeq值
- `[cseq]`：当前CSeq值（SIPP自动递增）
- `[len]`：自动计算Content-Length
- `[last_From:]`：使用最后的From头
- `[last_To:]`：使用最后的To头
- `[last_Call-ID:]`：使用最后的Call-ID

**CSeq自动递增说明**：
- SIPP工具会在每次发送消息时自动递增CSeq值
- 脚本中统一使用`[cseq]`，无需使用`[cseq+1]`、`[cseq+2]`等
- 例如：INVITE使用`[cseq]`，ACK也使用`[cseq]`，SIPP会自动递增为正确值

## SDP格式

### SDP结构
```xml
v=0                           // 协议版本
o=user1 53655765 2353687637 IN IP4 192.168.1.100  // 会话发起者
s=-                           // 会话名称
c=IN IP4 192.168.1.100       // 连接信息
t=0 0                         // 时间描述
m=audio 6000 RTP/AVP 0 8 101 // 媒体描述（音频，端口6000，RTP/AVP，编解码列表）
a=rtpmap:0 PCMU/8000          // PCMU编解码定义
a=rtpmap:8 PCMA/8000          // PCMA编解码定义
a=rtpmap:101 telephone-event/8000  // DTMF事件
a=fmtp:101 0-15               // DTMF事件范围
```

### 常用编解码
- `0`：PCMU（G.711 μ-law，8000Hz）
- `8`：PCMA（G.711 A-law，8000Hz）
- `9`：G.722
- `18`：G.729
- `101`：telephone-event（DTMF）

## 常见场景示例

### 场景1：基本呼叫流程（包含100 Trying）
**消息序列**：
1. UAC发送INVITE
2. UAS发送100 Trying（临时响应）
3. UAC接收100 Trying（可选）
4. UAS发送180 Ringing
5. UAC接收180 Ringing
6. UAC接收200 OK
7. UAC发送ACK
8. 等待通话时长（pause）
9. UAC发送BYE
10. UAC接收200 OK

**适用场景**：端到端呼叫测试、基本功能验证、需要检查临时响应的场景

**说明**：100 Trying是可选的临时响应，服务器可能在发送180之前发送100表示正在处理请求。

### 场景2：注册流程
**消息序列**：
1. UAC发送REGISTER
2. UAC接收401 Unauthorized（带WWW-Authenticate）
3. UAC发送REGISTER（带Authorization头）
4. UAC接收200 OK

**适用场景**：注册功能测试、认证机制验证

### 场景3：带认证的呼叫
**消息序列**：
1. UAC发送INVITE
2. UAC接收407 Proxy Authentication Required
3. UAC发送INVITE（带Proxy-Authorization）
4. UAC接收180 Ringing
5. UAC接收200 OK
6. UAC发送ACK
7. UAC发送BYE
8. UAC接收200 OK

**适用场景**：代理服务器认证测试

### 场景4：重定向测试
**消息序列**：
1. UAC发送INVITE
2. UAC接收302 Moved Temporarily（带Contact头指向新地址）
3. UAC发送ACK（针对302）
4. UAC发送INVITE（到新地址）
5. 正常呼叫流程

**适用场景**：SIP重定向功能测试

### 场景5：并发压力测试
**特点**：
- 使用基本呼叫模板
- 通过sipp命令行参数控制并发
- `-r`：呼叫速率（calls/sec）
- `-l`：最大并发数
- `-m`：总呼叫次数
- `-d`：通话时长（ms）

**适用场景**：性能测试、压力测试、容量规划

## 验证规则

### XML格式检查
- 所有标签必须闭合
- CDATA区域不能包含`]]>`序列
- 特殊字符需转义（`&` → `&amp;`，`<` → `&lt;`，`>` → `&gt;`）

### SIP消息格式检查
- 每行必须以CRLF（`\r\n`）结束
- Content-Length必须与实际内容匹配
- 必须包含必需的头部字段
- CSeq序列号必须递增

### 主被叫匹配检查
- UAC的send必须对应UAS的recv
- UAS的send必须对应UAC的recv
- Call-ID必须一致
- From/To标签必须正确传递

## 约束与注意事项

1. **变量替换**：SIPP内置变量在运行时替换，脚本中保持原样
2. **编码要求**：脚本文件必须使用UTF-8编码
3. **端口配置**：确保media_port与remote_port不冲突
4. **网络配置**：local_ip和media_ip应为实际可访问的IP地址
5. **时间单位**：pause的时间单位为毫秒（ms）
6. **重传机制**：可使用`retrans`属性控制重传间隔
7. **超时设置**：recv消息可设置`timeout`属性
