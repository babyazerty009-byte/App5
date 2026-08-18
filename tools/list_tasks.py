"""
Tools: List tasks and list overdue tasks from Bitrix24.
Uses server-side filtering for performance with large datasets.
"""

from langchain_core.tools import tool

# Status labels for Bitrix24 task statuses
STATUS_LABELS = {
    "1": "New",
    "2": "Pending",
    "3": "In Progress",
    "4": "Awaiting Validation",
    "5": "Completed",
    "6": "Deferred",
}

PRIORITY_LABELS = {
    "0": "Low",
    "1": "Normal",
    "2": "High",
}


def _resolve_group_names(tasks: list[dict]) -> dict:
    "Build a cache of group_id -> group_name for all groups referenced in tasks."
    from services.agent import client

    # Collect unique non-empty group IDs
    group_ids = set()
    for t in tasks:
        gid = t.get("group_id")
        if gid and str(gid) != "0":
            group_ids.add(int(gid))

    if not group_ids:
        return {}

    # Fetch all groups once and build lookup
    cache = {}
    try:
        groups = client.list_groups()
        for g in groups:
            if g["id"] in group_ids:
                cache[g["id"]] = g["name"]
    except Exception:
        pass  # If lookup fails, we simply won't show group names

    return cache


def _format_task_list(header: str, tasks: list[dict]) -> str:
    """Format a list of tasks for display."""
    if not tasks:
        return f"{header}\n📭 No tasks found."

    # Resolve group names once for all tasks
    group_names = _resolve_group_names(tasks)

    lines = [f"{header} ({len(tasks)} result{'s' if len(tasks) > 1 else ''}):\n"]
    for t in tasks:
        status = STATUS_LABELS.get(str(t.get("status", "")), t.get("status", "?"))
        priority = PRIORITY_LABELS.get(str(t.get("priority", "")), "")
        deadline = t.get("deadline") or "No deadline"
        tags = t.get("tags", [])
        tag_str = f" {','.join(tags)}" if tags else ""

        # Show group name only if the task belongs to a real group
        gid = t.get("group_id")
        if gid and str(gid) != "0":
            gname = group_names.get(int(gid), "")
            group = f" {gname}" if gname else ""
        else:
            group = ""

        lines.append(
            f"  #{t['id']:>4}  │ {status:<22} │ {priority:<12} │ {deadline:<22} │ {t['title']}{tag_str}{group}"
        )
    return "\n".join(lines)


@tool
def list_tasks(
    status: str = None, #new, pending, in_progress, completed, deferred, or all
    assignee_name: str = None, #first name of the assignee
    group_name: str = None, #name of the group
    limit: int = 20, #maximum number of tasks to return
) -> str:
    "List tasks from Bitrix24 with optional filters."
    from services.agent import client

    task_filter = {}

    # Status filter
    status_map = {
        "new": 1, "nouveau": 1,
        "pending": 2, "en_attente": 2,
        "in_progress": 3, "en_cours": 3,
        "awaiting_validation": 4, "validation": 4,
        "completed": 5, "terminé": 5, "termine": 5,
        "deferred": 6, "reporté": 6, "reporte": 6,
    }
    if status and status.lower() in status_map:
        task_filter["STATUS"] = status_map[status.lower()]

    # Assignee filter
    if assignee_name:
        users = client.search_user_by_name(assignee_name)
        if not users:
            return f" No user found with the name '{assignee_name}'."
        task_filter["RESPONSIBLE_ID"] = users[0]["id"]

    # Group filter
    if group_name:
        groups = client.search_group_by_name(group_name)
        if not groups:
            return f" No project/group found with the name '{group_name}'."
        task_filter["GROUP_ID"] = groups[0]["id"]

    # Clamp limit
    limit = min(max(1, limit), 100)

    tasks = client.list_tasks(
        filter=task_filter if task_filter else None,
        limit=limit,
    )
    return _format_task_list(" Task List", tasks)


@tool
def list_overdue_tasks(assignee_name: str = None) -> str: # assignee_name: Optional. Filter overdue tasks by assignee's first name.
    "List all overdue tasks from Bitrix24 (deadline passed, not completed)."
    from services.agent import client

    responsible_id = None
    if assignee_name:
        users = client.search_user_by_name(assignee_name)
        if not users:
            return f" No user found with the name '{assignee_name}'."
        responsible_id = users[0]["id"]

    tasks = client.list_overdue_tasks(responsible_id=responsible_id)
    if not tasks:
        return " No overdue tasks!"
    return _format_task_list(" Overdue Tasks", tasks)
