"""
monday_client.py
Monday.com GraphQL API wrapper for Skylark Drones BI Agent.
Handles schema detection, paginated item fetching, and retry logic.
"""

import os
import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"


class MondayAPIError(Exception):
    """Raised when Monday.com API returns an error."""
    pass


class MondayClient:
    """Read-only Monday.com GraphQL API client with retry and pagination."""

    def __init__(self, token: str = None):
        self.token = token or os.getenv("MONDAY_API_TOKEN", "")
        if not self.token:
            raise ValueError(
                "Monday.com API token not set. "
                "Add MONDAY_API_TOKEN to your .env file."
            )
        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "API-Version": "2023-10",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _execute(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query against Monday.com API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            resp = requests.post(
                MONDAY_API_URL,
                json=payload,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.HTTPError as e:
            if resp.status_code == 401:
                raise MondayAPIError(
                    "Invalid Monday.com API token. "
                    "Please check MONDAY_API_TOKEN in your .env file."
                )
            raise MondayAPIError(f"Monday.com API HTTP error: {e}")
        except requests.Timeout:
            raise MondayAPIError("Monday.com API request timed out. Please try again.")
        except requests.ConnectionError:
            raise MondayAPIError("Cannot reach Monday.com API. Check your internet connection.")

        data = resp.json()
        if "errors" in data and data["errors"]:
            err_msg = data["errors"][0].get("message", "Unknown error")
            raise MondayAPIError(f"Monday.com GraphQL error: {err_msg}")

        return data.get("data", {})

    def get_board_schema(self, board_id: str) -> dict:
        """
        Fetch the board's column definitions to dynamically detect schema.
        Returns a dict: {column_id: {title, type}}
        """
        query = """
        query ($boardId: [ID!]) {
          boards(ids: $boardId) {
            id
            name
            columns {
              id
              title
              type
            }
          }
        }
        """
        data = self._execute(query, {"boardId": [str(board_id)]})
        boards = data.get("boards", [])
        if not boards:
            raise MondayAPIError(
                f"Board {board_id} not found. "
                "Check DEALS_BOARD_ID / WORKORDERS_BOARD_ID in your .env file."
            )
        board = boards[0]
        schema = {
            "board_id": board["id"],
            "board_name": board["name"],
            "columns": {col["id"]: {"title": col["title"], "type": col["type"]} for col in board["columns"]},
        }
        return schema

    def get_board_items(self, board_id: str, limit: int = 500) -> list:
        """
        Fetch all items from a board with cursor-based pagination.
        Returns a flat list of item dicts with column_values unpacked.
        """
        all_items = []
        cursor = None

        while True:
            if cursor:
                query = """
                query ($boardId: [ID!], $limit: Int, $cursor: String!) {
                  boards(ids: $boardId) {
                    items_page(limit: $limit, cursor: $cursor) {
                      cursor
                      items {
                        id
                        name
                        column_values {
                          id
                          text
                          value
                        }
                      }
                    }
                  }
                }
                """
                variables = {"boardId": [str(board_id)], "limit": limit, "cursor": cursor}
            else:
                query = """
                query ($boardId: [ID!], $limit: Int) {
                  boards(ids: $boardId) {
                    items_page(limit: $limit) {
                      cursor
                      items {
                        id
                        name
                        column_values {
                          id
                          text
                          value
                        }
                      }
                    }
                  }
                }
                """
                variables = {"boardId": [str(board_id)], "limit": limit}

            data = self._execute(query, variables)
            boards = data.get("boards", [])
            if not boards:
                break

            page = boards[0].get("items_page", {})
            items = page.get("items", [])

            for item in items:
                flat = {"_item_id": item["id"], "_item_name": item["name"]}
                for cv in item.get("column_values", []):
                    flat[cv["id"]] = cv.get("text") or cv.get("value") or ""
                all_items.append(flat)

            cursor = page.get("cursor")
            if not cursor or not items:
                break

        return all_items

    def get_board_data(self, board_id: str) -> tuple:
        """
        Convenience: fetch schema + items together.
        Returns (schema_dict, items_list)
        """
        schema = self.get_board_schema(board_id)
        items = self.get_board_items(board_id)
        return schema, items

    def validate_connection(self) -> dict:
        """Test API token validity by fetching the current user."""
        query = "{ me { id name email } }"
        data = self._execute(query)
        return data.get("me", {})
