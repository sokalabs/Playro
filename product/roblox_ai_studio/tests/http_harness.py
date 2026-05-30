"""HTTP test server harness for Playro API integration tests."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from product.roblox_ai_studio.app import api


class PlayroApiServer:
    """Threaded Playro API server bound to an ephemeral localhost port."""

    def __init__(
        self,
        *,
        output_root: Path | None = None,
        token: str = "test-token",
    ) -> None:
        self.output_root = output_root
        self.token = token
        self.port = 0
        self._server: api.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._orig_token: str | None = None
        self._orig_output_root: Path | None = None

    def start(self) -> "PlayroApiServer":
        self._orig_token = api.os.environ.get("PLAYRO_API_TOKEN")
        api.os.environ["PLAYRO_API_TOKEN"] = self.token
        if self.output_root is not None:
            self._orig_output_root = api.DEFAULT_OUTPUT_ROOT
            api.DEFAULT_OUTPUT_ROOT = self.output_root
        self._server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.RobloxAIStudioHandler)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join()
        if self._orig_output_root is not None:
            api.DEFAULT_OUTPUT_ROOT = self._orig_output_root
        if self._orig_token is None:
            api.os.environ.pop("PLAYRO_API_TOKEN", None)
        else:
            api.os.environ["PLAYRO_API_TOKEN"] = self._orig_token

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "PlayroApiServer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


@contextmanager
def playro_api_server(*, output_root: Path | None = None, token: str = "test-token") -> Iterator[PlayroApiServer]:
    server = PlayroApiServer(output_root=output_root, token=token)
    try:
        yield server.start()
    finally:
        server.stop()
