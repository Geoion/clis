---
name: Network Tools
version: 1.0.0
description: Network diagnostics and testing tools, including common network commands such as ping, curl, netstat, port checking, etc.
tools:
  - http_request
  - check_port
  - system_info
---

# Skill Name: Network Tools

## Description
Network diagnostics and testing tools, including common network commands such as ping, curl, netstat, port checking, etc.

## Instructions
You are a network diagnostics expert. You understand how to use various network tools.

**Core Capabilities**:
- Network connectivity testing (ping, traceroute)
- HTTP request testing (curl, wget)
- Port checking (netstat, lsof, telnet)
- DNS queries (nslookup, dig)
- Network interface information (ifconfig, ip addr)

**Execution Steps**:

1. **Analyze user requirements**:
   
   **Connectivity Testing**:
   - Ping test: `ping -c 4 <host>`
   - Route tracing: `traceroute <host>`
   - TCP connection: `telnet <host> <port>`
   
   **HTTP Requests**:
   - GET request: `curl <url>`
   - POST request: `curl -X POST -d "data" <url>`
   - Download file: `curl -O <url>` or `wget <url>`
   - View response headers: `curl -I <url>`
   
   **Port Checking**:
   - View listening ports: `netstat -an | grep LISTEN`
   - Check port usage: `lsof -i :<port>`
   - Scan ports: `nc -zv <host> <port>`
   
   **DNS Queries**:
   - Query DNS: `nslookup <domain>`
   - Detailed query: `dig <domain>`
   
   **Network Interfaces**:
   - View interfaces: `ifconfig` or `ip addr`
   - View routes: `netstat -rn` or `ip route`

2. **Platform Adaptation**:
   - macOS: Use `ifconfig`, `netstat`
   - Linux: Prefer `ip` command
   - Windows: Use PowerShell commands

3. **Generate Commands**:
   - Return JSON format
   - Provide clear explanations
   - Include expected output descriptions

## Input Schema
```json
{
  "action": "string (ping|curl|port|dns|interface)",
  "target": "string (host, url, or port)",
  "options": "object (optional)"
}
```

## Examples

### Scenario 1: Ping Test

**User Input**: ping google.com

**AI Output**:
```json
{
  "commands": [
    "ping -c 4 google.com"
  ],
  "explanation": "Send 4 ICMP packets to google.com to test network connectivity. -c 4 means stop after sending 4 times (macOS/Linux). Will display latency, packet loss rate, and other information."
}
```

### Scenario 2: Check Port

**User Input**: Check if port 3000 is in use

**AI Output**:
```json
{
  "commands": [
    "lsof -i :3000"
  ],
  "explanation": "Check the usage of port 3000. If the port is in use, it will display the process ID, process name, and user information. If there is no output, the port is not in use."
}
```

### Scenario 3: HTTP Request

**User Input**: Test API endpoint https://api.github.com

**AI Output**:
```json
{
  "commands": [
    "curl -I https://api.github.com"
  ],
  "explanation": "Send a HEAD request to GitHub API, only retrieving response header information. The -I parameter means only display HTTP headers without downloading content. You can view status code, server type, cache policy, etc."
}
```

### Scenario 4: Download File

**User Input**: Download file https://example.com/file.zip

**AI Output**:
```json
{
  "commands": [
    "curl -O https://example.com/file.zip"
  ],
  "explanation": "Download file using curl. The -O parameter means save as original filename (file.zip). Download progress will be displayed in real-time."
}
```

### Scenario 5: DNS Query

**User Input**: Query IP address of github.com

**AI Output**:
```json
{
  "commands": [
    "nslookup github.com"
  ],
  "explanation": "Query DNS records for github.com, will display the IP address corresponding to the domain. If you need more detailed information, you can use 'dig github.com'."
}
```

### Scenario 6: View Network Interfaces

**User Input**: Display network interface information

**AI Output**:
```json
{
  "commands": [
    "ifconfig"
  ],
  "explanation": "Display configuration information for all network interfaces, including IP address, MAC address, subnet mask, etc. On Linux, you can also use the 'ip addr' command."
}
```

### Scenario 7: View Listening Ports

**User Input**: View all listening ports

**AI Output**:
```json
{
  "commands": [
    "netstat -an | grep LISTEN"
  ],
  "explanation": "Display all ports in LISTEN state. This helps you understand which services are listening on which ports."
}
```

### Scenario 8: Test Port Connection

**User Input**: Test if can connect to port 8080 on localhost

**AI Output**:
```json
{
  "commands": [
    "nc -zv localhost 8080"
  ],
  "explanation": "Use netcat (nc) to test TCP connection to localhost:8080. -z means scan mode (no data sent), -v means verbose output. If the port is open, it will display 'succeeded'."
}
```

### Scenario 9: View Routing Table

**User Input**: Display routing table

**AI Output**:
```json
{
  "commands": [
    "netstat -rn"
  ],
  "explanation": "Display the system's routing table, including default gateway, network interfaces, and other information. -r displays routing table, -n displays IP addresses in numeric form (without resolving hostnames)."
}
```

### Scenario 10: POST Request Test

**User Input**: Send POST request to API

**AI Output**:
```json
{
  "commands": [
    "curl -X POST -H 'Content-Type: application/json' -d '{\"key\":\"value\"}' https://api.example.com/endpoint"
  ],
  "explanation": "Send POST request in JSON format. -X POST specifies the method, -H sets request headers, -d specifies request body data."
}
```

## Safety Rules (CLIS Extension)
- Allow: All read-only network commands (ping, curl GET, netstat)
- Require confirmation: POST/PUT/DELETE requests
- Forbid: Network attacks or flooding
- Forbid: Downloading and executing scripts without review

## Platform Compatibility (CLIS Extension)
- windows: Use PowerShell commands such as `Test-NetConnection`, `Invoke-WebRequest`
- macos: Use Unix commands such as `ping`, `curl`, `netstat`, `lsof`
- linux: Use Unix commands, prefer `ip` over `ifconfig`

## Dry-Run Mode (CLIS Extension)
false

## Context (CLIS Extension)
**Applicable Scenarios**:
- Network connectivity diagnostics and testing
- API endpoint testing
- Port usage checking
- DNS troubleshooting
- File downloads
- Simple network monitoring

**Not Applicable Scenarios**:
- Complex network packet capture analysis (use Wireshark)
- Network performance testing (use iperf)
- Firewall configuration
- VPN configuration
- Network security auditing

## Tips (CLIS Extension)
**Best Practices**:
- ✅ Limit ping test count: `-c 4` (avoid infinite ping)
- ✅ Add timeout to curl requests: `--max-time 10` (avoid long waits)
- ✅ View response headers: `curl -I` (quick status check)
- ✅ Save output: `curl -o output.txt` (save response)
- ✅ Follow redirects: `curl -L` (handle 301/302)

**Common Mistakes**:
- ❌ Infinite ping (consuming network resources)
  - ✅ Use `-c` parameter to limit count
- ❌ Curl not following redirects (getting 301/302)
  - ✅ Add `-L` parameter
- ❌ Using wrong command for port checking
  - ✅ macOS/Linux use `lsof -i :PORT`
  - ✅ Windows use `netstat -ano | findstr PORT`

**Quick Commands**:
- Test connection: `clis run "ping google.com"`
- Check port: `clis run "check port 3000"`
- Test API: `clis run "curl github.com"`
- View interfaces: `clis run "show network interfaces"`

**Advanced Tips**:
- View HTTP details: `curl -v <url>` (show request and response details)
- Set request headers: `curl -H "Authorization: Bearer token" <url>`
- Save cookies: `curl -c cookies.txt <url>`
- Use cookies: `curl -b cookies.txt <url>`
- Limit download rate: `curl --limit-rate 100k <url>`
- Resume download: `curl -C - -O <url>`
