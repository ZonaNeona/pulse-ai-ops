"""MCPServer (FastMCP stdio) exposing Pulse tools for Hermes Agent.

Launched by Hermes profile or any MCP-compatible AI agent.
Uses the unified tool registry from pulse.agents.tools.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from pulse.agents import tools

server = MCPServer("pulse-ops")


# Register all tools from the unified registry into the MCP server
@server.tool(
    name="sales_pulse",
    description="Получить сводный пульс продаж за сегодня: ключевые KPI, выручку к плану, количество аномалий.",
)
def mcp_sales_pulse() -> dict[str, Any]:
    return tools.tool_sales_pulse()


@server.tool(
    name="get_signals",
    description="Активные сигналы РОПа: пропущенные звонки, зависшие сделки, просрочки.",
)
def mcp_get_signals(limit: int = 10, severity: str = "") -> list[dict[str, Any]]:
    return tools.tool_get_signals(limit, severity)


@server.tool(
    name="team_status",
    description="Статус менеджеров: звонки, нормы, время разговора, оценка качества и отставания.",
)
def mcp_team_status() -> list[dict[str, Any]]:
    return tools.tool_team_status()



@server.tool(
    name="get_deals",
    description="Получить список сделок CRM с фильтрацией по стадии, менеджеру или признаку застревания.",
)
def mcp_get_deals(
    stage: str = "", manager: str = "", stale_only: bool = False, limit: int = 20
) -> list[dict[str, Any]]:
    return tools.tool_get_deals(stage, manager, stale_only, limit)


@server.tool(
    name="deal_details",
    description="Получить подробную информацию по конкретной сделке CRM по её ID.",
)
def mcp_deal_details(deal_id: int) -> dict[str, Any]:
    return tools.tool_deal_details(deal_id)


@server.tool(
    name="call_review",
    description="Получить аналитический разбор звонка: оценка 0-100, критерии чек-листа, цитаты из речи и совет РОПа.",
)
def mcp_call_review(call_id: int) -> dict[str, Any]:
    return tools.tool_call_review(call_id)


@server.tool(
    name="reconciliation",
    description="Сверить продажи CRM (Битрикс24) с реализациями в 1С: суммы и список расхождений.",
)
def mcp_reconciliation() -> dict[str, Any]:

    return tools.tool_reconciliation()


@server.tool(
    name="erp_stock",
    description="Проверить остатки и резервы оборудования на складе в 1С.",
)
def mcp_erp_stock(query: str = "") -> list[dict[str, Any]]:
    return tools.tool_erp_stock(query)


@server.tool(
    name="draft_task",
    description="Сформировать черновик задачи в CRM. Действие выполняется ТОЛЬКО после подтверждения пользователем.",
)
def mcp_draft_task(
    title: str, responsible: str, deal_id: int | None = None, deadline_days: int = 1
) -> dict[str, Any]:
    return tools.tool_draft_task(title, responsible, deal_id, deadline_days)


@server.tool(
    name="confirm_draft",
    description="Подтвердить применение ранее созданного черновика (Human-in-the-loop).",
)
def mcp_confirm_draft(draft_id: str) -> dict[str, Any]:
    return tools.tool_confirm_draft(draft_id)


@server.tool(
    name="undo_draft",
    description="Отменить черновик задачи или изменения.",
)
def mcp_undo_draft(draft_id: str) -> dict[str, Any]:
    return tools.tool_undo_draft(draft_id)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
