# OPS-Agent - 智能运维助手

基于 LangChain 的智能业务代理系统，支持 RAG 知识库和 AIOps 智能运维。

## 功能特性

- **智能对话**：基于 LangChain 的多轮对话，支持上下文理解
- **RAG 知识库**：支持文档上传、向量化检索、混合搜索（BM25 + 语义）
- **AIOps 智能运维**：自动规划运维任务，支持 Prometheus 告警查询、日志分析
- **MCP 服务集成**：支持接入外部 MCP 服务器扩展工具能力
- **Web 界面**：内置前端界面，支持实时对话和文件管理

## 技术栈

- **后端**：FastAPI + LangChain + LangGraph
- **向量数据库**：Milvus
- **LLM**：DashScope (Qwen) / OpenAI 兼容接口
- **前端**：原生 HTML/CSS/JS

## 快速开始

### 1. 环境要求

- Python 3.11+
- Milvus 向量数据库
- DashScope API Key

### 2. 安装依赖

```bash
uv sync
```

### 3. 启动 Milvus

```bash
docker compose -f vector-database.yml up -d
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

### 5. 启动服务

```bash
python -m app.main
```

访问 http://localhost:9900

## License

MIT