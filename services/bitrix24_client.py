"""
Bitrix24 REST API Client — High Performance Edition.
Handles CRUD operations for tasks and user lookup via webhook.
Optimized for large datasets with server-side filtering and pagination.
"""

import time
import requests
from datetime import datetime
from config import BITRIX24_WEBHOOK_URL


class Bitrix24Client:
    "Client to interact with the Bitrix24 REST API via webhook."
    def __init__(self, webhook_url: str = None):
        self.webhook_url = (webhook_url or BITRIX24_WEBHOOK_URL).rstrip("/")

    
    #  Generic API caller
    def _call(self, method: str, params: dict = None) -> dict:
        """Call a Bitrix24 REST method and return the JSON response."""
        url = f"{self.webhook_url}/{method}"
        try:
            response = requests.post(url, json=params or {}, timeout=15)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise Exception(
                    f"Bitrix24 error [{data['error']}]: "
                    f"{data.get('error_description', 'Unknown error')}"
                )
            return data
        except requests.RequestException as e:
            raise ConnectionError(f"Connection error to Bitrix24: {e}")

    def _call_with_retry(self, method: str, params: dict = None, max_retries: int = 3) -> dict:
        "Call Bitrix24 with automatic retry on rate-limit (429) errors."
        for attempt in range(max_retries):
            try:
                return self._call(method, params)
            except Exception as e:
                error_str = str(e)
                if "QUERY_LIMIT_EXCEEDED" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 1.0  # 1s, 2s, 3s
                        time.sleep(wait_time)
                        continue
                raise

    
    #  Paginated API caller (for large datasets)
    def _call_paginated(
        self,
        method: str,
        params: dict,
        result_key: str = "tasks",
        max_items: int = 200,
    ) -> list:
        """
        Paginate through results using start=-1 + >ID filter.
        - start=-1 disables COUNT calculation (much faster)
        - >ID filter ensures stable traversal
        """
        all_items = []
        last_id = 0
        params = dict(params)  # Don't mutate the original

        while len(all_items) < max_items:
            # Set up pagination parameters
            page_params = dict(params)
            page_params["start"] = -1

            # Add >ID filter for pagination
            page_filter = dict(page_params.get("filter", {}))
            page_filter[">ID"] = last_id
            page_params["filter"] = page_filter

            # Ensure ordered by ID ascending for stable pagination
            page_params["order"] = {"ID": "asc"}

            data = self._call_with_retry(method, page_params)
            result = data.get("result", {})

            # Handle both dict results (tasks) and list results
            if isinstance(result, dict):
                items = result.get(result_key, [])
            elif isinstance(result, list):
                items = result
            else:
                break

            if not items:
                break

            all_items.extend(items)

            # Get the last ID for next page
            last_item = items[-1]
            last_id = int(last_item.get("id") or last_item.get("ID", 0))

            # If we got fewer than 50 items, we've reached the end
            if len(items) < 50:
                break

        return all_items[:max_items]

    
    #  Users
    def search_user_by_name(self, name: str) -> list[dict]:
        "Search for a user by first name or last name. Returns a list of dicts: {id, name, last_name, email}."
        # Search by first name
        data = self._call_with_retry(
            "user.search",
            {"FILTER": {"NAME": f"{name}%"}}
        )
        users = data.get("result", [])

        # If no results by first name, try last name
        if not users:
            data = self._call_with_retry(
                "user.search",
                {"FILTER": {"LAST_NAME": f"{name}%"}}
            )
            users = data.get("result", [])

        return [
            {
                "id": int(u["ID"]),
                "name": u.get("NAME", ""),
                "last_name": u.get("LAST_NAME", ""),
                "email": u.get("EMAIL", ""),
            }
            for u in users
        ]

    def get_current_user(self) -> dict:
        "Return info about the current user (webhook owner)."
        data = self._call("user.current")
        u = data.get("result", {})
        return {
            "id": int(u["ID"]),
            "name": u.get("NAME", ""),
            "last_name": u.get("LAST_NAME", ""),
        }

    
    #  Tasks — Create
    def create_task(
        self,
        title: str,
        responsible_id: int,
        deadline: str = None,
        description: str = "",
        group_id: int = None,
        priority: int = None,
        tags: list = None,
    ) -> dict:
        """
        Create a task.
        - title: task title
        - responsible_id: user ID of the assignee
        - deadline: ISO date string (e.g. "2026-08-15T18:00:00")
        - description: optional description
        - group_id: optional project/group ID
        - priority: 0=low, 1=normal, 2=high
        - tags: optional list of tag strings
        Returns the created task info.
        """
        fields = {
            "TITLE": title,
            "RESPONSIBLE_ID": responsible_id,
        }
        if deadline:
            fields["DEADLINE"] = deadline
        if description:
            fields["DESCRIPTION"] = description
        if group_id:
            fields["GROUP_ID"] = group_id
        if priority is not None:
            fields["PRIORITY"] = priority
        if tags:
            fields["TAGS"] = tags

        data = self._call_with_retry("tasks.task.add", {"fields": fields})
        task = data.get("result", {}).get("task", {})
        return {
            "id": task.get("id"),
            "title": task.get("title"),
            "responsible_id": task.get("responsibleId"),
            "deadline": task.get("deadline"),
            "status": task.get("status"),
        }

   
    #  Tasks — List (with server-side filtering)
    def list_tasks(
        self,
        filter: dict = None,
        limit: int = 20,
        order: dict = None,
    ) -> list[dict]:
        """
        List tasks with server-side filtering.
        
        filter examples:
          {"RESPONSIBLE_ID": 42}           — tasks assigned to user 42
          {"<DEADLINE": "2026-08-15...", "!STATUS": 5}  — overdue
          {"%TITLE": "scanner"}            — title contains "scanner"
          {"GROUP_ID": 10}                 — tasks in project/group 10
          {"STATUS": 3}                    — in progress
          {"TAG": "urgent"}               — tasks with tag "urgent"
        """
        params = {
            "select": [
                "ID", "TITLE", "STATUS", "DEADLINE",
                "RESPONSIBLE_ID", "CREATED_DATE", "GROUP_ID",
                "PRIORITY", "TAGS", "DESCRIPTION",
            ],
        }
        if filter:
            params["filter"] = filter
        if order:
            params["order"] = order

        # For small limits, use a single call
        if limit <= 50:
            params["start"] = 0
            data = self._call_with_retry("tasks.task.list", params)
            tasks = data.get("result", {}).get("tasks", [])
            return [self._format_task(t) for t in tasks[:limit]]
        else:
            # For larger requests, use pagination
            tasks = self._call_paginated(
                "tasks.task.list", params, result_key="tasks", max_items=limit
            )
            return [self._format_task(t) for t in tasks]

    def list_overdue_tasks(self, responsible_id: int = None) -> list[dict]:
        "List overdue tasks (deadline passed, not completed)."
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        task_filter = {
            "<DEADLINE": now,
            "!STATUS": 5,  # 5 = completed
        }
        if responsible_id:
            task_filter["RESPONSIBLE_ID"] = responsible_id

        return self.list_tasks(
            filter=task_filter,
            order={"DEADLINE": "asc"},
            limit=50,
        )

    
    #  Tasks — Get single
    def get_task(self, task_id: int) -> dict:
        "Get a task by its ID."
        data = self._call_with_retry(
            "tasks.task.get",
            {
                "taskId": task_id,
                "select": [
                    "ID", "TITLE", "STATUS", "DEADLINE",
                    "RESPONSIBLE_ID", "CREATED_DATE", "DESCRIPTION",
                    "GROUP_ID", "PRIORITY", "TAGS",
                ],
            },
        )
        task = data.get("result", {}).get("task", {})
        return self._format_task(task)

    
    #  Tasks — Update
    def update_task(self, task_id: int, fields: dict) -> bool:
        """
        Update a task.
        fields can contain: TITLE, DEADLINE, DESCRIPTION, RESPONSIBLE_ID,
        STATUS, GROUP_ID, PRIORITY, TAGS, etc.
        """
        try:
            self._call_with_retry(
                "tasks.task.update",
                {"taskId": int(task_id), "fields": fields}
            )
            return True
        except Exception as e:
            if "400" in str(e) or "NOT_FOUND" in str(e):
                raise Exception(f"Task #{task_id} not found.")
            raise

    
    #  Tasks — Delete
    def delete_task(self, task_id: int) -> bool:
        "Delete a task by its ID."
        try:
            self._call_with_retry(
                "tasks.task.delete",
                {"taskId": int(task_id)}
            )
            return True
        except Exception as e:
            if "400" in str(e) or "NOT_FOUND" in str(e):
                raise Exception(f"Task #{task_id} not found.")
            raise

    #  Projects / Groups — List
    def list_groups(self) -> list[dict]:
        """List all workgroups/projects."""
        data = self._call_with_retry(
            "sonet_group.get",
            {"FILTER": {"ACTIVE": "Y"}}
        )
        groups = data.get("result", [])
        return [
            {
                "id": int(g["ID"]),
                "name": g.get("NAME", ""),
                "description": g.get("DESCRIPTION", ""),
            }
            for g in groups
        ]

    def search_group_by_name(self, name: str) -> list[dict]:
        """Search for a project/group by name."""
        data = self._call_with_retry(
            "sonet_group.get",
            {"FILTER": {"%NAME": name, "ACTIVE": "Y"}}
        )
        groups = data.get("result", [])
        return [
            {
                "id": int(g["ID"]),
                "name": g.get("NAME", ""),
                "description": g.get("DESCRIPTION", ""),
            }
            for g in groups
        ]

    
    #  Helpers
    @staticmethod
    def _format_task(t: dict) -> dict:
        """Normalize the task representation."""
        return {
            "id": t.get("id") or t.get("ID"),
            "title": t.get("title") or t.get("TITLE", ""),
            "status": t.get("status") or t.get("STATUS", ""),
            "deadline": t.get("deadline") or t.get("DEADLINE", ""),
            "responsible_id": t.get("responsibleId") or t.get("RESPONSIBLE_ID", ""),
            "created": t.get("createdDate") or t.get("CREATED_DATE", ""),
            "group_id": t.get("groupId") or t.get("GROUP_ID", ""),
            "priority": t.get("priority") or t.get("PRIORITY", ""),
            "tags": t.get("tags") or t.get("TAGS", []),
            "description": t.get("description") or t.get("DESCRIPTION", ""),
        }
