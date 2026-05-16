"""MiniMax Hailuo video generation adapter with SSRF-safe async polling."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from ._security import sanitize_error as _sanitize_error
from .exceptions import LLMError

logger = logging.getLogger(__name__)

_SUBMIT_URL = "https://api.minimax.io/v1/video_generation"
_POLL_BASE = "https://api.minimax.io/v1/query/video_generation"

_TERMINAL_STATUSES = {"Success", "Fail"}
_PENDING_STATUSES = {"Queueing", "Processing"}


class HailuoAdapter:
    """MiniMax Hailuo video generation adapter.

    Submits a generation task and polls the fixed status endpoint until
    the task reaches a terminal state. The polling URL is always constructed
    from the known fixed base — never from any URL returned in the API
    response body — preventing SSRF attacks.

    Requires `httpx` (optional dependency). Install with:
        pip install mcp-common[llm]
    """

    def __init__(
        self,
        api_key: str,
        model: str = "video-01",
        poll_interval: float = 5.0,
        max_poll_seconds: float = 300.0,
    ) -> None:
        if httpx is None:
            msg = (
                "httpx package required for HailuoAdapter. "
                "Install with: pip install mcp-common[llm]"
            )
            raise ImportError(msg)

        self._api_key = api_key
        self._model = model
        self._poll_interval = poll_interval
        self._max_poll_seconds = max_poll_seconds

    def _poll_url(self, task_id: str) -> str:
        """Return the fixed polling URL for a task. Never follows URLs from response bodies."""
        return f"{_POLL_BASE}?task_id={task_id}"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Submit a video generation task and poll until complete.

        Args:
            prompt: Text description for the video.
            **kwargs: Additional parameters forwarded to the submit body
                      (e.g. duration, resolution).

        Returns:
            Dict with 'task_id', 'file_id', 'status'.

        Raises:
            LLMError: On API error, task failure, or poll timeout.
        """
        payload: dict[str, Any] = {"model": self._model, "prompt": prompt, **kwargs}

        async with httpx.AsyncClient(headers=self._auth_headers()) as client:
            try:
                submit_resp = await client.post(_SUBMIT_URL, json=payload)
                submit_resp.raise_for_status()
            except Exception as e:
                raise LLMError(
                    f"Hailuo submit failed: {_sanitize_error(str(e))}"
                ) from e

            submit_data = submit_resp.json()
            task_id: str = submit_data["task_id"]
            logger.debug("Hailuo task submitted: %s", task_id)

            deadline = time.monotonic() + self._max_poll_seconds

            while True:
                if time.monotonic() >= deadline:
                    raise LLMError(
                        f"Hailuo video generation timed out after {self._max_poll_seconds}s "
                        f"(task_id={task_id})"
                    )

                try:
                    poll_resp = await client.get(self._poll_url(task_id))
                    poll_resp.raise_for_status()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    raise LLMError(
                        f"Hailuo poll failed: {_sanitize_error(str(e))}"
                    ) from e

                poll_data = poll_resp.json()
                status: str = poll_data.get("status", "")

                if status == "Success":
                    logger.debug("Hailuo task complete: %s", task_id)
                    return {
                        "task_id": task_id,
                        "file_id": poll_data.get("file_id", ""),
                        "status": status,
                    }

                if status == "Fail":
                    base_resp = poll_data.get("base_resp", {})
                    msg = base_resp.get("status_msg", "unknown error")
                    raise LLMError(
                        f"Hailuo video generation task failed: {msg} (task_id={task_id})"
                    )

                await asyncio.sleep(self._poll_interval)
