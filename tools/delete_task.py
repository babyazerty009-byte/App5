
from langchain_core.tools import tool


@tool
def delete_task(task_id: int) -> str:
    "Delete a task from Bitrix24 by its ID."
    from services.agent import client

    if not task_id:
        return " Please specify the task ID to delete."

    # Try to get the task title before deleting
    try:
        task = client.get_task(task_id)
        title = task.get("title", "")
    except Exception:
        title = ""

    try:
        client.delete_task(task_id)
    except Exception as e:
        return f" Error: {e}"

    msg = f" Task #{task_id} deleted."
    if title:
        msg += f" ({title})"
    return msg
