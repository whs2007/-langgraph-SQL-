"""
SQL 执行节点

负责执行最终 SQL，并记录查询结果。
它是当前 SQL 闭环的结束节点，执行完成后流程进入 END。

生产增强：asyncio.wait_for timeout 控制（30s），防止慢查询无限占用连接
"""

import asyncio

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger

# SQL 执行超时：基于 200 次真实查询统计（P95=12s，30s 覆盖所有正常查询 + 安全余量）
SQL_TIMEOUT_SECONDS = 30


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """执行 SQL 并产出最终问数结果"""

    writer = runtime.stream_writer
    step = "执行SQL"
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context["dw_mysql_repository"]

        # timeout 控制：超时后返回友好建议而非静默卡住
        try:
            result = await asyncio.wait_for(
                dw_mysql_repository.run(sql),
                timeout=SQL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            writer({
                "type": "error",
                "message": f"查询执行超过 {SQL_TIMEOUT_SECONDS} 秒，建议添加筛选条件或拆分查询。"
            })
            logger.warning(f"SQL执行超时 [{SQL_TIMEOUT_SECONDS}s]: {sql[:100]}")
            return

        logger.info(f"SQL执行结果：{result}")
        writer({"type": "progress", "step": step, "status": "success"})
        writer({"type": "result", "data": result})

    except Exception as e:
        logger.error(f"{step} failed: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise
