

from langchain_core.tools import tool


@tool
def find_user(name: str) -> str:
    "Search for a Bitrix24 user by their first name or last name.Returns the user's ID, name, and email. Use this tool when you need to find a user's ID before creating,updating, or filtering tasks."
    from services.agent import client

    if not name or not name.strip():
        return " Please provide a name to search for."

    users = client.search_user_by_name(name.strip())

    if not users:
        return f" No user found matching '{name}'."

    lines = [f" Users matching '{name}' ({len(users)} found):\n"]
    for u in users:
        lines.append(
            f"  • ID {u['id']:>4} : {u['name']} {u['last_name']}"
            + (f" — {u['email']}" if u.get('email') else "")
        )
    return "\n".join(lines)
