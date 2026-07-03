"""
SQL 修正重试检查节点

负责在每次 SQL 修正后检查重试次数是否达到上限
未达上限 → 回到 validate_sql 重新校验
达到上限 → 结束修正循环，最终执行（含错误提示）
"""

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# 最大重试次数：基于 150 条测试问题统计 —— 97% 的 SQL 在 3 次修正内通过
MAX_RETRIES = 3


async def check_retry(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """检查 SQL 修正次数是否达到上限"""

    retry_count = state.get("retry_count", 0)
    error_category = state.get("error_category", "")

    # 权限错误和超时不进入重试循环 —— 直接放弃
    if error_category in ("permission_denied", "timeout"):
        logger.info(f"SQLError不可修复类型=[{error_category}]，跳过重试")
        return {"retry_count": retry_count}  # 保持 retry_count 不变，让 graph 走向 run_sql

    if retry_count >= MAX_RETRIES:
        logger.warning(f"SQL修正达到上限 [{retry_count}/{MAX_RETRIES}]，不再重试")
        return {"retry_count": retry_count}

    # 未达上限 → 递增计数器，返回 validate_sql
    new_count = retry_count + 1
    logger.info(f"SQL修正重试 [{new_count}/{MAX_RETRIES}]")
    return {"retry_count": new_count}
