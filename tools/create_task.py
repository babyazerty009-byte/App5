
import re
from datetime import datetime, timedelta
from langchain_core.tools import tool



#  Date resolution helpers
DAYS_FR = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

DAYS_EN = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

MONTHS_FR = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
    "novembre": 11, "décembre": 12, "decembre": 12,
}


def _next_weekday(target_weekday: int) -> datetime:
    "Return the date of the next given weekday (0=Monday)."
    today = datetime.now()
    delta = (target_weekday - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def resolve_date(text: str) -> str | None:
    "Convert a date expression (French or English) to an ISO datetime string."
    if not text:
        return None

    t = text.lower().strip()

    # French weekdays
    for day_name, day_num in DAYS_FR.items():
        if day_name in t:
            dt = _next_weekday(day_num)
            return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")

    # English weekdays
    for day_name, day_num in DAYS_EN.items():
        if day_name in t:
            dt = _next_weekday(day_num)
            return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")

    # Relative expressions (French + English)
    if ("tomorrow" in t or ("demain" in t and "après" not in t)):
        dt = datetime.now() + timedelta(days=1)
        return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    if "après-demain" in t or "après demain" in t or "day after tomorrow" in t:
        dt = datetime.now() + timedelta(days=2)
        return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
    if "aujourd'hui" in t or "today" in t:
        dt = datetime.now()
        return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")

    # Absolute date (e.g. "15/08/2026")
    date_match = re.search(r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})", t)
    if date_match:
        try:
            from dateutil import parser as dateutil_parser
            dt = dateutil_parser.parse(date_match.group(1), dayfirst=True)
            return dt.replace(hour=18, minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass

    # French months (e.g. "20 août")
    for month_name, month_num in MONTHS_FR.items():
        match = re.search(rf"(\d{{1,2}})\s*{month_name}", t)
        if match:
            day_num = int(match.group(1))
            year = datetime.now().year
            try:
                dt = datetime(year, month_num, day_num, 18, 0, 0)
                if dt < datetime.now():
                    dt = datetime(year + 1, month_num, day_num, 18, 0, 0)
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    return None


@tool
def create_task(
    title: str,
    assignee_name: str = None, #The first name of the person to assign the task to. If not provided, the task is assigned to the current user.
    deadline: str = None, #A date expression for the deadline (e.g. 'friday', 'tomorrow', 'lundi', '15/08/2026'). If not provided, no deadline is set.
    description: str = None, #An optional detailed description for the task.
    group_name: str = None, #Optional name of the project/group to assign the task to.
    priority: str = None, #Priority level: 'low', 'normal', or 'high'.
    tags: str = None, #Comma-separated list of tags (e.g. 'urgent,IT,maintenance').
) -> str:
    "Create a new task in Bitrix24."
    from services.agent import client 

    # Resolve the assignee
    responsible_id = None
    responsible_display = "current user"

    if assignee_name:
        users = client.search_user_by_name(assignee_name)
        if not users:
            return f"No user found with the name '{assignee_name}'."
        if len(users) > 1:
            user_list = "\n".join(
                f"  • ID {u['id']}: {u['name']} {u['last_name']} ({u['email']})"
                for u in users
            )
            return f"Multiple users found for '{assignee_name}':\n{user_list}\nPlease specify the full name."
        responsible_id = users[0]["id"]
        responsible_display = f"{users[0]['name']} {users[0]['last_name']}".strip()
    else:
        current = client.get_current_user()
        responsible_id = current["id"]

    # Resolve the deadline
    resolved_deadline = resolve_date(deadline) if deadline else None

    # Resolve the group/project
    group_id = None
    if group_name:
        groups = client.search_group_by_name(group_name)
        if groups:
            group_id = groups[0]["id"]
        else:
            return f"No project/group found with the name '{group_name}'."

    # Resolve priority
    priority_map = {"low": 0, "normal": 1, "high": 2, "basse": 0, "normale": 1, "haute": 2}
    resolved_priority = priority_map.get(priority.lower()) if priority else None

    # Resolve tags
    resolved_tags = [t.strip() for t in tags.split(",")] if tags else None

    # Create the task
    task = client.create_task(
        title=title,
        responsible_id=responsible_id,
        deadline=resolved_deadline,
        description=description or "",
        group_id=group_id,
        priority=resolved_priority,
        tags=resolved_tags,
    )

    response = (
        f" Task created successfully!\n"
        f"    ID       : {task['id']}\n"
        f"    Title    : {task['title']}\n"
        f"    Assigned : {responsible_display}"
    )
    if resolved_deadline:
        response += f"\n    Deadline : {resolved_deadline}"
    if group_id:
        response += f"\n    Project  : {group_name}"
    if resolved_tags:
        response += f"\n    Tags     : {', '.join(resolved_tags)}"
    if resolved_priority is not None:
        labels = {0: "Low", 1: "Normal", 2: "High"}
        response += f"\n    Priority : {labels.get(resolved_priority, priority)}"
    return response
