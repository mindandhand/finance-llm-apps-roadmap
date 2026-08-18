from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CubeApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"Cube API returned HTTP {status}: {message}")
        self.status = status


class CubeConnectionError(RuntimeError):
    pass


class CubeClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        timeout: float = 10.0,
        transport: Callable[..., Any] = urlopen,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.transport = transport

    def meta(self) -> dict[str, Any]:
        return self._get("/cubejs-api/v1/meta")

    def load(self, query: dict[str, Any]) -> dict[str, Any]:
        encoded = urlencode({"query": json.dumps(query, separators=(",", ":"))})
        return self._get(f"/cubejs-api/v1/load?{encoded}")

    def _get(self, path: str) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = self.token
        request = Request(f"{self.base_url}{path}", headers=headers)
        try:
            with self.transport(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(body).get("error", body)
            except json.JSONDecodeError:
                message = body
            raise CubeApiError(error.code, str(message)) from error
        except URLError as error:
            raise CubeConnectionError(str(error.reason)) from error


if __name__ == "__main__":
    import os

    client = CubeClient(f"http://127.0.0.1:{os.getenv('CUBE_PORT', '4000')}")
    cubes = [cube["name"] for cube in client.meta()["cubes"]]
    result = client.load({"measures": ["transactions.weighted_average_price"]})
    print("public cubes:", cubes)
    print("REST result:", result["data"])
