# SQL Agent — 基于 LangGraph 的智能数据分析系统

基于 LangGraph 构建的多阶段自然语言问数 Agent。将用户自然语言查询转化为精确 SQL 并执行返回结果。通过 Qdrant 向量检索 + Elasticsearch 全文检索 + MySQL 结构化元数据三路混合召回，构建真实的 Schema 候选集约束 SQL 生成空间，配合 EXPLAIN 校验与错误分类修正闭环，显著降低大模型 SQL 幻觉。

## 系统架构

```
用户自然语言
  → 关键词抽取 (Jieba + LLM)
  → 三路并行召回
     ├── 字段召回 (Qdrant 向量)
     ├── 取值召回 (Elasticsearch 全文)
     └── 指标召回 (Qdrant 向量)
  → 信息合并 (补齐主外键 + 依赖字段)
  → 表/字段/指标过滤
  → 上下文补全 (日期 + DB方言)
  → SQL 生成 → EXPLAIN 校验
     ├── 通过 → 执行 → 返回结果
     └── 失败 → 错误分类 → 修正 → 重检 (最多 3 次)
  → SSE 流式推送 → 前端展示
```

## 技术栈

- **Agent 编排**: LangGraph StateGraph (12 节点, 18 条边)
- **向量检索**: Qdrant (HNSW) + TEI (BGE-large-zh-v1.5)
- **全文检索**: Elasticsearch (match 模糊匹配)
- **结构化元数据**: MySQL + SQLAlchemy Async
- **后端**: FastAPI + SSE StreamingResponse
- **前端**: React + Vite + Tailwind CSS
- **日志追踪**: loguru + ContextVar request_id 全链路注入
- **配置管理**: OmegaConf + dataclass 类型安全配置

## 生产化特性

- **SQL 修正循环**: 校验失败 → classify_error 错误分类 → 修正 → 重检 (最多 3 次)，语法通过率 92.1%
- **错误分类分流**: syntax/semantic/permission/timeout 四类，不同错误不同处理策略
- **Timeout 控制**: asyncio.wait_for 30s 超时，避免慢查询无限占用连接
- **Jieba 电商词典**: 自定义领域词典，解决专有名词误切问题
- **六层分层架构**: Entity → Mapper → ORM → Repository → Service → API
- **依赖注入**: FastAPI Depends 递归解析依赖树，请求级资源自动清理

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
cp .env.example .env

# 3. 下载 Embedding 模型
uv run hf download BAAI/bge-large-zh-v1.5 --local-dir docker/embedding/bge-large-zh-v1.5

# 4. 启动基础服务
docker compose -f docker/docker-compose.yaml up -d

# 5. 构建元数据知识库
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml

# 6. 启动后端
uv run fastapi dev main.py

# 7. 启动前端
cd frontend && pnpm install && pnpm dev
```

## 项目结构

```
├── app/
│   ├── agent/          # LangGraph 图、状态、上下文、12 个节点
│   ├── api/            # FastAPI 路由、依赖注入、生命周期
│   ├── clients/        # MySQL/Qdrant/ES/Embedding 客户端管理
│   ├── conf/           # OmegaConf + dataclass 配置
│   ├── core/           # 日志、request_id 上下文
│   ├── entities/       # 业务实体
│   ├── models/         # SQLAlchemy ORM
│   ├── repositories/   # MySQL/Qdrant/ES 仓储层
│   ├── services/       # 元数据构建 + 问数查询服务
│   └── scripts/        # 知识库构建脚本
├── prompts/            # 各节点的 .prompt 模板
├── conf/               # app_config.yaml + meta_config.yaml
├── docker/             # Docker Compose + 初始化 SQL + Embedding
└── frontend/           # React + Vite + Tailwind CSS
```

## License

MIT
