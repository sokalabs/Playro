"""Tests for SSE event framing in build_events.py.

Verifies that BuildEvent.to_sse() emits properly named SSE event types
(``event: stage``, ``event: complete``, ``event: error``) so that the
desktop EventSource listeners (addEventListener('stage', ...), etc.)
receive the frames. Also confirms that data-only parsing still works
via the JSON payload's ``stage`` field for onmessage fallbacks.
"""

import json
import socket
import threading
import time
import unittest

from product.roblox_ai_studio.app.build_events import BuildEvent, BuildEventBus, _STAGE_TO_EVENT


def _make_event(stage: str, **overrides) -> BuildEvent:
    """Helper to create a BuildEvent with sensible defaults."""
    defaults = {
        "build_id": "build_test",
        "stage": stage,
        "title": f"Stage: {stage}",
        "detail": f"Detail for {stage}",
        "timestamp": 1700000000.0,
    }
    defaults.update(overrides)
    return BuildEvent(**defaults)


class TestBuildEventToSseFraming(unittest.TestCase):
    """Test BuildEvent.to_sse() emits named SSE event types."""

    def test_progress_stages_emit_event_stage(self):
        """idea, plan, luau, handoff should all emit 'event: stage'."""
        for stage in ("idea", "plan", "luau", "handoff"):
            event = _make_event(stage)
            sse = event.to_sse()
            self.assertTrue(
                sse.startswith("event: stage\n"),
                f"stage={stage!r} should produce 'event: stage', got: {sse!r}",
            )

    def test_complete_stage_emits_event_complete(self):
        event = _make_event("complete")
        sse = event.to_sse()
        self.assertTrue(
            sse.startswith("event: complete\n"),
            f"complete should produce 'event: complete', got: {sse!r}",
        )

    def test_error_stage_emits_event_error(self):
        event = _make_event("error")
        sse = event.to_sse()
        self.assertTrue(
            sse.startswith("event: error\n"),
            f"error should produce 'event: error', got: {sse!r}",
        )

    def test_unknown_stage_defaults_to_event_stage(self):
        event = _make_event("unknown_custom_stage")
        sse = event.to_sse()
        self.assertTrue(
            sse.startswith("event: stage\n"),
            f"unknown stage should default to 'event: stage', got: {sse!r}",
        )

    def test_sse_frame_has_data_line_after_event_line(self):
        event = _make_event("plan")
        sse = event.to_sse()
        lines = sse.split("\n")
        self.assertEqual(lines[0], "event: stage")
        self.assertTrue(lines[1].startswith("data: "), f"Second line should be data:, got: {lines[1]!r}")

    def test_sse_frame_ends_with_double_newline(self):
        event = _make_event("plan")
        sse = event.to_sse()
        self.assertTrue(sse.endswith("\n\n"), f"SSE frame must end with \\n\\n, got: {sse!r}")

    def test_json_payload_includes_stage_field(self):
        """The JSON payload should still contain 'stage' for onmessage fallback routing."""
        event = _make_event("luau")
        sse = event.to_sse()
        data_line = [l for l in sse.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[len("data: "):])
        self.assertEqual(payload["stage"], "luau")

    def test_json_payload_complete_event_has_stage(self):
        event = _make_event("complete")
        sse = event.to_sse()
        data_line = [l for l in sse.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[len("data: "):])
        self.assertEqual(payload["stage"], "complete")

    def test_json_payload_includes_optional_data(self):
        event = _make_event("luau", data={"generated_files": ["a.lua", "b.lua"]})
        sse = event.to_sse()
        data_line = [l for l in sse.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[len("data: "):])
        self.assertIn("data", payload)
        self.assertEqual(payload["data"]["generated_files"], ["a.lua", "b.lua"])

    def test_payload_has_all_required_fields(self):
        event = _make_event("plan", build_id="b_123", title="Plan Rojo project", detail="Preparing folders", timestamp=42.0)
        sse = event.to_sse()
        data_line = [l for l in sse.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[len("data: "):])
        self.assertEqual(payload["build_id"], "b_123")
        self.assertEqual(payload["stage"], "plan")
        self.assertEqual(payload["title"], "Plan Rojo project")
        self.assertEqual(payload["detail"], "Preparing folders")
        self.assertEqual(payload["timestamp"], 42.0)


class TestBuildEventBusSubscribeEmit(unittest.TestCase):
    """Test that BuildEventBus emits and subscribers receive events."""

    def test_subscriber_receives_emitted_event(self):
        test_bus = BuildEventBus(ttl_seconds=60)
        q = test_bus.subscribe("build_test")
        event = _make_event("plan")
        test_bus.emit(event)
        received = q.get_nowait()
        self.assertEqual(received.stage, "plan")
        self.assertEqual(received.build_id, "build_test")

    def test_subscriber_event_formats_correctly_via_to_sse(self):
        test_bus = BuildEventBus(ttl_seconds=60)
        q = test_bus.subscribe("build_test")
        event = _make_event("complete", data={"ok": True})
        test_bus.emit(event)
        received = q.get_nowait()
        sse = received.to_sse()
        self.assertTrue(sse.startswith("event: complete\n"))
        data_line = [l for l in sse.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[len("data: "):])
        self.assertTrue(payload["data"]["ok"])

    def test_unsubscribe_prevents_future_delivery(self):
        test_bus = BuildEventBus(ttl_seconds=60)
        q = test_bus.subscribe("build_test")
        test_bus.unsubscribe("build_test", q)
        event = _make_event("idea")
        test_bus.emit(event)
        self.assertTrue(q.empty())


class TestSSEEndpointFraming(unittest.TestCase):
    """Integration test: the SSE HTTP endpoint writes named-event frames.

    Verifies that GET /generate/<build_id>/events returns text/event-stream
    with frames that include ``event: stage`` / ``event: complete`` headers,
    matching what the desktop EventSource addEventListener('stage', ...)
    expects. This directly tests the regression the reviewer found (data-only
    frames with no event: line).
    """

    @classmethod
    def setUpClass(cls):
        """Start a one-shot HTTP server for SSE endpoint tests."""
        from product.roblox_ai_studio.app import api
        from product.roblox_ai_studio.tests.http_harness import PlayroApiServer

        cls._api = api
        cls._orig_output_root = api.DEFAULT_OUTPUT_ROOT
        cls._orig_emit = api._emit
        cls._api_server = PlayroApiServer()
        cls._api_server.start()
        cls._port = cls._api_server.port

    @classmethod
    def tearDownClass(cls):
        cls._api_server.stop()

    def _connect_sse(self, build_id, timeout=10):
        """Open an SSE connection and return (conn, resp)."""
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=timeout)
        conn.request("GET", f"/generate/{build_id}/events", headers={"X-Playro-API-Token": "test-token"})
        resp = conn.getresponse()
        return conn, resp

    def _read_sse_body(self, resp, timeout=8):
        """Read the SSE response body with timeout-aware raw socket reads."""
        body = b""
        deadline = time.time() + timeout
        try:
            raw = resp.fp
            while hasattr(raw, "raw"):
                raw = raw.raw
            if hasattr(raw, "settimeout"):
                raw.settimeout(2)
            while time.time() < deadline:
                try:
                    chunk = raw.recv(4096)
                    if not chunk:
                        break
                    body += chunk
                    if b"event: complete" in body or b"event: error" in body:
                        time.sleep(0.3)
                        break
                except (socket.timeout, TimeoutError, OSError):
                    break
        except Exception:
            try:
                body = resp.read()
            except Exception:
                pass
        finally:
            try:
                resp.close()
            except Exception:
                pass
        return body.decode("utf-8", errors="replace")

    def test_sse_endpoint_returns_event_stream_content_type(self):
        """SSE response must have Content-Type: text/event-stream."""
        build_id = "build_abcdEFGH0123_-abcdEFGH0001_"
        conn, resp = self._connect_sse(build_id)
        self.assertEqual(resp.status, 200)
        ct = resp.getheader("Content-Type", "")
        self.assertEqual(ct, "text/event-stream")

        # Emit a complete event so the stream terminates
        self._api.event_bus.emit(BuildEvent(
            build_id=build_id, stage="complete", title="Done",
            detail="test", timestamp=time.time(),
        ))
        self._read_sse_body(resp)

    def test_sse_endpoint_emits_named_event_headers(self):
        """SSE frames must include event: lines for stage/complete/error.

        This is the core regression test: the reviewer found that the SSE
        stream produced only data: lines, which means addEventListener
        ('stage', ...) never fires on the desktop. After the fix, every
        frame should start with ``event: <type>``.
        """
        build_id = "build_abcdEFGH0123_-abcdEFGH0002_"

        # Connect to the SSE stream FIRST, then emit events in a
        # background thread so the subscriber queue is active.
        conn, resp = self._connect_sse(build_id)
        self.assertEqual(resp.status, 200)

        stages = [
            ("idea", "Read prompt", "Got it"),
            ("plan", "Plan project", "Planning"),
            ("luau", "Write Luau", "Writing"),
            ("complete", "Build complete", "Done"),
        ]

        def _emit_events():
            time.sleep(0.3)
            for stage, title, detail in stages:
                self._api.event_bus.emit(BuildEvent(
                    build_id=build_id, stage=stage, title=title,
                    detail=detail, timestamp=time.time(),
                ))

        emitter = threading.Thread(target=_emit_events, daemon=True)
        emitter.start()
        body = self._read_sse_body(resp, timeout=8)
        emitter.join(timeout=5)

        # Split into SSE frames (separated by double newlines)
        frames = [f.strip() for f in body.split("\n\n") if f.strip()]
        self.assertGreaterEqual(len(frames), 4, f"Expected at least 4 frames, got {len(frames)}: {frames!r}")

        # Verify each frame has an event: line
        event_types = []
        for frame in frames:
            lines = frame.strip().split("\n")
            event_line = [l for l in lines if l.startswith("event: ")]
            self.assertTrue(
                len(event_line) > 0,
                f"Frame missing 'event:' line: {frame!r}",
            )
            event_types.append(event_line[0].removeprefix("event: "))

        # idea/plan/luau -> "stage", complete -> "complete"
        self.assertIn("stage", event_types, "No 'event: stage' frame found -- desktop addEventListener('stage', ...) won't fire")
        self.assertIn("complete", event_types, "No 'event: complete' frame found -- desktop addEventListener('complete', ...) won't fire")

    def test_sse_complete_frame_includes_project_id_in_payload(self):
        """The complete event's JSON payload should include project_id
        so the desktop can fetch the full project record."""
        build_id = "build_abcdEFGH0123_-abcdEFGH0003_"

        # Connect first, then emit
        conn, resp = self._connect_sse(build_id)
        self.assertEqual(resp.status, 200)

        def _emit_events():
            time.sleep(0.3)
            self._api.event_bus.emit(BuildEvent(
                build_id=build_id, stage="plan", title="Plan",
                detail="planning", timestamp=time.time(),
            ))
            self._api.event_bus.emit(BuildEvent(
                build_id=build_id, stage="complete", title="Done",
                detail="finished", timestamp=time.time(),
                data={"project_id": "test-proj-42", "ok": True, "files": ["a.lua"]},
            ))

        emitter = threading.Thread(target=_emit_events, daemon=True)
        emitter.start()
        body = self._read_sse_body(resp, timeout=8)
        emitter.join(timeout=5)

        # Find the complete frame
        frames = [f.strip() for f in body.split("\n\n") if f.strip()]
        complete_frames = []
        for frame in frames:
            lines = frame.strip().split("\n")
            for l in lines:
                if l.startswith("event: complete"):
                    complete_frames.append(frame)
                    break

        self.assertTrue(len(complete_frames) > 0, "No complete event frame found")
        # Parse the data line from the complete frame
        data_lines = [l for l in complete_frames[0].split("\n") if l.startswith("data: ")]
        self.assertTrue(len(data_lines) > 0, "Complete frame missing data: line")
        payload = json.loads(data_lines[0].removeprefix("data: "))
        self.assertEqual(payload.get("data", {}).get("project_id"), "test-proj-42",
                         "Complete event payload should carry project_id for desktop project fetch")


if __name__ == "__main__":
    unittest.main()
