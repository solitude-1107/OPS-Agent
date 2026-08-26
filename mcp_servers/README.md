# MCP Servers

为 AIOps 智能诊断提供日志查询和监控数据工具。

## CLS Server (cls_server.py)
日志查询服务 - 端口 8003

## Monitor Server (monitor_server.py)
监控数据服务 - 端口 8004

## 快速开始
```bash
pip install fastmcp
python mcp_servers/cls_server.py
python mcp_servers/monitor_server.py
```

## 注意: 当前版本返回模拟数据，生产环境需配置真实 API。