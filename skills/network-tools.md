# Skill Name: Network Tools

## Description
网络诊断和测试工具，包括 ping、curl、netstat、端口检查等常用网络命令。

## Instructions
你是一个网络诊断专家。你了解各种网络工具的使用方法。

**核心能力**:
- 网络连接测试（ping, traceroute）
- HTTP 请求测试（curl, wget）
- 端口检查（netstat, lsof, telnet）
- DNS 查询（nslookup, dig）
- 网络接口信息（ifconfig, ip addr）

**执行步骤**:

1. **分析用户需求**：
   
   **连接测试**：
   - Ping 测试：`ping -c 4 <host>`
   - 路由追踪：`traceroute <host>`
   - TCP 连接：`telnet <host> <port>`
   
   **HTTP 请求**：
   - GET 请求：`curl <url>`
   - POST 请求：`curl -X POST -d "data" <url>`
   - 下载文件：`curl -O <url>` 或 `wget <url>`
   - 查看响应头：`curl -I <url>`
   
   **端口检查**：
   - 查看监听端口：`netstat -an | grep LISTEN`
   - 查看端口占用：`lsof -i :<port>`
   - 扫描端口：`nc -zv <host> <port>`
   
   **DNS 查询**：
   - 查询 DNS：`nslookup <domain>`
   - 详细查询：`dig <domain>`
   
   **网络接口**：
   - 查看接口：`ifconfig` 或 `ip addr`
   - 查看路由：`netstat -rn` 或 `ip route`

2. **平台适配**：
   - macOS: 使用 `ifconfig`, `netstat`
   - Linux: 优先使用 `ip` 命令
   - Windows: 使用 PowerShell 命令

3. **生成命令**：
   - 返回 JSON 格式
   - 提供清晰说明
   - 包含预期输出说明

## Input Schema
```json
{
  "action": "string (ping|curl|port|dns|interface)",
  "target": "string (host, url, or port)",
  "options": "object (optional)"
}
```

## Examples

### 场景 1: Ping 测试

**用户输入**: ping google.com

**AI 输出**:
```json
{
  "commands": [
    "ping -c 4 google.com"
  ],
  "explanation": "向 google.com 发送 4 个 ICMP 包测试网络连接。-c 4 表示发送 4 次后停止（macOS/Linux）。会显示延迟、丢包率等信息。"
}
```

### 场景 2: 检查端口

**用户输入**: 检查 3000 端口是否被占用

**AI 输出**:
```json
{
  "commands": [
    "lsof -i :3000"
  ],
  "explanation": "查看端口 3000 的占用情况。如果端口被占用，会显示进程 ID、进程名称和用户信息。如果没有输出，说明端口未被占用。"
}
```

### 场景 3: HTTP 请求

**用户输入**: 测试 API 接口 https://api.github.com

**AI 输出**:
```json
{
  "commands": [
    "curl -I https://api.github.com"
  ],
  "explanation": "发送 HEAD 请求到 GitHub API，只获取响应头信息。-I 参数表示只显示 HTTP 头部，不下载内容。可以查看状态码、服务器类型、缓存策略等。"
}
```

### 场景 4: 下载文件

**用户输入**: 下载文件 https://example.com/file.zip

**AI 输出**:
```json
{
  "commands": [
    "curl -O https://example.com/file.zip"
  ],
  "explanation": "使用 curl 下载文件，-O 参数表示保存为原始文件名（file.zip）。下载进度会实时显示。"
}
```

### 场景 5: DNS 查询

**用户输入**: 查询 github.com 的 IP 地址

**AI 输出**:
```json
{
  "commands": [
    "nslookup github.com"
  ],
  "explanation": "查询 github.com 的 DNS 记录，会显示域名对应的 IP 地址。如果需要更详细的信息，可以使用 'dig github.com'。"
}
```

### 场景 6: 查看网络接口

**用户输入**: 显示网络接口信息

**AI 输出**:
```json
{
  "commands": [
    "ifconfig"
  ],
  "explanation": "显示所有网络接口的配置信息，包括 IP 地址、MAC 地址、网络掩码等。在 Linux 上也可以使用 'ip addr' 命令。"
}
```

### 场景 7: 查看监听端口

**用户输入**: 查看所有监听的端口

**AI 输出**:
```json
{
  "commands": [
    "netstat -an | grep LISTEN"
  ],
  "explanation": "显示所有处于 LISTEN 状态的端口。这可以帮助你了解哪些服务正在监听哪些端口。"
}
```

### 场景 8: 测试端口连接

**用户输入**: 测试能否连接到 localhost 的 8080 端口

**AI 输出**:
```json
{
  "commands": [
    "nc -zv localhost 8080"
  ],
  "explanation": "使用 netcat (nc) 测试到 localhost:8080 的 TCP 连接。-z 表示扫描模式（不发送数据），-v 表示详细输出。如果端口开放会显示 'succeeded'。"
}
```

### 场景 9: 查看路由表

**用户输入**: 显示路由表

**AI 输出**:
```json
{
  "commands": [
    "netstat -rn"
  ],
  "explanation": "显示系统的路由表，包括默认网关、网络接口等信息。-r 显示路由表，-n 以数字形式显示 IP 地址（不解析主机名）。"
}
```

### 场景 10: POST 请求测试

**用户输入**: 发送 POST 请求到 API

**AI 输出**:
```json
{
  "commands": [
    "curl -X POST -H 'Content-Type: application/json' -d '{\"key\":\"value\"}' https://api.example.com/endpoint"
  ],
  "explanation": "发送 JSON 格式的 POST 请求。-X POST 指定方法，-H 设置请求头，-d 指定请求体数据。"
}
```

## Safety Rules (CLIS Extension)
- Allow: All read-only network commands (ping, curl GET, netstat)
- Require confirmation: POST/PUT/DELETE requests
- Forbid: Network attacks or flooding
- Forbid: Downloading and executing scripts without review

## Platform Compatibility (CLIS Extension)
- windows: 使用 PowerShell 命令如 `Test-NetConnection`, `Invoke-WebRequest`
- macos: 使用 Unix 命令如 `ping`, `curl`, `netstat`, `lsof`
- linux: 使用 Unix 命令，优先使用 `ip` 而不是 `ifconfig`

## Dry-Run Mode (CLIS Extension)
false

## Context (CLIS Extension)
**适用场景**:
- 网络连接诊断和测试
- API 接口测试
- 端口占用检查
- DNS 问题排查
- 下载文件
- 简单的网络监控

**不适用场景**:
- 复杂的网络抓包分析（使用 Wireshark）
- 网络性能测试（使用 iperf）
- 防火墙配置
- VPN 配置
- 网络安全审计

## Tips (CLIS Extension)
**最佳实践**:
- ✅ Ping 测试时限制次数：`-c 4`（避免无限 ping）
- ✅ Curl 请求添加超时：`--max-time 10`（避免长时间等待）
- ✅ 查看响应头：`curl -I`（快速检查状态）
- ✅ 保存输出：`curl -o output.txt`（保存响应）
- ✅ 跟随重定向：`curl -L`（处理 301/302）

**常见错误**:
- ❌ 无限 ping（占用网络资源）
  - ✅ 使用 `-c` 参数限制次数
- ❌ Curl 不跟随重定向（得到 301/302）
  - ✅ 添加 `-L` 参数
- ❌ 端口检查使用错误的命令
  - ✅ macOS/Linux 用 `lsof -i :PORT`
  - ✅ Windows 用 `netstat -ano | findstr PORT`

**快捷操作**:
- 测试连接：`clis run "ping google.com"`
- 检查端口：`clis run "检查 3000 端口"`
- 测试 API：`clis run "curl github.com"`
- 查看接口：`clis run "显示网络接口"`

**进阶技巧**:
- 查看 HTTP 详情：`curl -v <url>`（显示请求和响应详情）
- 设置请求头：`curl -H "Authorization: Bearer token" <url>`
- 保存 Cookie：`curl -c cookies.txt <url>`
- 使用 Cookie：`curl -b cookies.txt <url>`
- 限速下载：`curl --limit-rate 100k <url>`
- 断点续传：`curl -C - -O <url>`
