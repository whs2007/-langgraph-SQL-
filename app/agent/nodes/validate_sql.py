"""
SQL 校验节点

负责在真正执行查询前，用数据库解析一次生成的 SQL
校验结果不在这里决定流程走向，而是通过 state["error"] 交给 graph.py 的条件边判断

生产增强：classify_error 错误分类机制 —— 不同错误类型触发不同处理策略
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository


# SQL 错误分类常量
class SQLErrorCategory:
    SYNTAX = "syntax_error"       # 语法错误 → 可自动修复
    SEMANTIC = "semantic_error"   # 语义错误（字段/表不存在）→ 可尝试修复
    PERMISSION = "permission_denied"  # 权限错误 → 不可修复，拒绝执行
    TIMEOUT = "timeout"           # 超时 → 建议简化查询
    UNKNOWN = "unknown"


def classify_error(error_msg: str) -> str:
    """根据 MySQL 报错信息分类 SQL 错误类型，用于分流处理"""
    error_lower = error_msg.lower()
    if "syntax error" in error_lower or "parse error" in error_lower:
        return SQLErrorCategory.SYNTAX
    if "unknown column" in error_lower or "doesn't exist" in error_lower:
        return SQLErrorCategory.SEMANTIC
    if "access denied" in error_lower or "command denied" in error_lower:
        return SQLErrorCategory.PERMISSION
    if "timeout" in error_lower or "lock wait" in error_lower:
        return SQLErrorCategory.TIMEOUT
    return SQLErrorCategory.UNKNOWN


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """校验 SQL，并返回 error 字段控制后续条件分支"""

    writer = runtime.stream_writer
    step = "校验SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository: DWMySQLRepository = runtime.context["dw_mysql_repository"]

        try:
            await dw_mysql_repository.validate(sql)
            writer({"type": "progress", "step": step, "status": "success"})
            logger.info("SQL语法正确")
            return {"error": None, "error_category": None}
        except Exception as e:
            error_msg = str(e)
            category = classify_error(error_msg)
            logger.info(f"SQL错误分类=[{category}] 详情={error_msg}")

            # 权限错误不可自动修复 —— 直接标记为成功（不走修正循环）
            if category == SQLErrorCategory.PERMISSION:
                writer({"type": "progress", "step": step, "status": "success"})
                return {"error": error_msg, "error_category": category}
            # 超时错误建议用户简化而非自动修正
            elif category == SQLErrorCategory.TIMEOUT:
                writer({"type": "progress", "step": step, "status": "success"})
                return {"error": error_msg, "error_category": category}
            # 语法/语义错误可尝试自动修正
            else:
                writer({"type": "progress", "step": step, "status": "success"})
                return {"error": error_msg, "error_category": category}

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
