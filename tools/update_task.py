
from langchain_core.tools import tool
from tools.create_task import resolve_date

@tool
def update_task(
    task_id: int ,# The ID of the task to update.
    new_deadline: str = None,# New deadline date expression (e.g. 'monday', 'friday', 'tomorrow', '20/08/2026').
    new_title: str = None,# New title for the task.
    new_description: str = None,# New description for the task.
    new_status: str = None,# New status: 'new', 'pending', 'in_progress', 'completed', or 'deferred'.
    new_priority: str = None,# New priority: 'low', 'normal', or 'high'.
    new_assignee_name: str = None,# First name of the new assignee.
    new_group_name: str = None,# Name of the project/group to move the task to.
    new_tags: str = None,# list of tags (e.g. 'urgent,IT').
) -> str:
    "Update an existing task in Bitrix24. Supports updating title, deadline, description, status, priority, project, tags, and assignee."
    from services.agent import client

    if not task_id:
        return " Please specify the task ID to update."

    fields = {}
    changes = []

    # Deadline
    if new_deadline:
        resolved = resolve_date(new_deadline)
        if resolved:
            fields["DEADLINE"] = resolved
            changes.append(f" New deadline: {resolved}")
        else:
            return f" Could not parse the date: '{new_deadline}'."

    # Title
    if new_title:
        fields["TITLE"] = new_title
        changes.append(f" New title: {new_title}")

    # Description
    if new_description:
        fields["DESCRIPTION"] = new_description
        changes.append(f" Description updated")

    # Status
    if new_status:
        status_map = {
            "new": 2, "nouveau": 2,
            "pending": 2, "en_attente": 2,
            "in_progress": 3, "en_cours": 3,
            "completed": 5, "terminé": 5, "termine": 5, "done": 5,
            "deferred": 6, "reporté": 6, "reporte": 6,
        }
        status_val = status_map.get(new_status.lower())
        if status_val:
            fields["STATUS"] = status_val
            changes.append(f" New status: {new_status}")
        else:
            return f" Unknown status: '{new_status}'. Use: new, pending, in_progress, completed, deferred."

    # Priority
    if new_priority:
        priority_map = {
            "low": 0, "basse": 0,
            "normal": 1, "normale": 1,
            "high": 2, "haute": 2,
        }
        priority_val = priority_map.get(new_priority.lower())
        if priority_val is not None:
            fields["PRIORITY"] = priority_val
            changes.append(f" New priority: {new_priority}")
        else:
            return f" Unknown priority: '{new_priority}'. Use: low, normal, high."

    # Assignee
    if new_assignee_name:
        users = client.search_user_by_name(new_assignee_name)
        if not users:
            return f" No user found with the name '{new_assignee_name}'."
        if len(users) > 1:
            user_list = "\n".join(
                f"  • ID {u['id']}: {u['name']} {u['last_name']}"
                for u in users
            )
            return f" Multiple users found for '{new_assignee_name}':\n{user_list}"
        fields["RESPONSIBLE_ID"] = users[0]["id"]
        changes.append(
            f" New assignee: {users[0]['name']} {users[0]['last_name']}"
        )

    # Group / Project
    if new_group_name:
        groups = client.search_group_by_name(new_group_name)
        if not groups:
            return f" No project/group found with the name '{new_group_name}'."
        fields["GROUP_ID"] = groups[0]["id"]
        changes.append(f" New project: {groups[0]['name']}")

    # Tags
    if new_tags:
        tag_list = [t.strip() for t in new_tags.split(",")]
        fields["TAGS"] = tag_list
        changes.append(f" New tags: {', '.join(tag_list)}")

    if not fields:
        return " Please specify what to update (deadline, title, description, status, priority, assignee, project, or tags)."

    try:
        client.update_task(task_id, fields)
    except Exception as e:
        return f" Error: {e}"

    response = f" Task #{task_id} updated:"
    for change in changes:
        response += f"\n   {change}"
    return response
