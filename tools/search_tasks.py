"""
Tool: Search tasks by keyword in Bitrix24.
Uses server-side %TITLE% filter for efficient search in large datasets.
"""

from langchain_core.tools import tool


@tool
def search_tasks(keyword: str, limit: int = 20) -> str: #keyword: The keyword to search for in task titles.
    """Search for tasks in Bitrix24 by keyword in the title.
    This searches on the Bitrix24 server, so it works efficiently
    even with millions of tasks.
    """
    from services.agent import client

    if not keyword or not keyword.strip():
        return "Please provide a keyword to search for."

    # Clamp limit
    limit = min(max(1, limit), 100)

    # Server-side search using %TITLE filter
    tasks = client.list_tasks(
        filter={"%TITLE": keyword.strip()},
        limit=limit,
    )

    if not tasks:
        return f" No tasks found matching '{keyword}'."

    # Format results
    lines = [f"Search results for '{keyword}' ({len(tasks)} found):\n"]
    for t in tasks:
        from tools.list_tasks import STATUS_LABELS
        status = STATUS_LABELS.get(str(t.get("status", "")), t.get("status", "?"))
        deadline = t.get("deadline") or "No deadline"
        lines.append(
            f"  #{t['id']:>4}  │ {status:<22} │ {deadline:<22} │ {t['title']}"
        )
    return "\n".join(lines)
