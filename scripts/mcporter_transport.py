"""The second way the probing scripts reach the platform: ONE long-lived mcporter runtime.

Every probing script calls a tool as `cmd /c npx mcporter call battlegrid-anbu.<tool> --output json --args -`: a new
Node process, config load and MCP session per call (about 40 s a call on 2026-11-11, a CPU-starved host; 240 hints took
162 minutes and the contract moved under the read). With EXTRACTION_TRANSPORT=runtime a script sends the same call
through scripts/mcporter_runtime.mjs instead: one process, one session, a JSON line in and a JSON line out.

    from scripts.mcporter_transport import RUNTIME, TRANSPORT
    if TRANSPORT == "runtime":
        stdout_text, stderr_text = RUNTIME.send(tool, args, timeout)      # TimeoutError on a timeout

`send` answers in the CLI process's own terms - the JSON the tool answered as stdout text, or empty stdout and the
reason as stderr text - so a script's answer rules (classify, the OAuth / outage / rate-limit patterns) read either
transport unchanged. Measured 2026-11-11: 235 of 235 hints read through both are identical.

The helper never starts an interactive authorization (`disableOAuth`): a call that needs one fails with the server's
message, which the scripts' AUTH_MARKERS stop on. scripts/refresh_metric_contracts.py carries its own copy of this
class because it runs standalone (its tests copy it alone into a throwaway tree).

    EXTRACTION_TRANSPORT   cli (default) | runtime
    MCPORTER_DIST          <...>/node_modules/mcporter when the package is not resolvable from scripts/ (the npx cache)
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import threading

TRANSPORT = os.environ.get("EXTRACTION_TRANSPORT") or "cli"
if TRANSPORT not in ("cli", "runtime"):
    raise SystemExit(f"EXTRACTION_TRANSPORT is {TRANSPORT!r}: 'cli' or 'runtime'")
HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcporter_runtime.mjs")


class Runtime:
    """One helper process, started on the first send and restarted after a timeout (the late answer of a timed-out
    call could arrive under the next call's id)."""

    def __init__(self, helper: str = HELPER):
        self.helper = helper
        self.p = self.lines = self.errors = None
        self.n = 0

    @staticmethod
    def _pump(stream, sink):
        for raw in iter(stream.readline, b""):
            sink.put(raw.decode("utf-8", errors="replace"))
        sink.put(None)

    def _stderr_tail(self) -> str:
        tail = []
        while self.errors is not None and not self.errors.empty():
            line = self.errors.get_nowait()
            if line:
                tail.append(line.strip())
        return " | ".join(tail)[-400:]

    def _line(self, timeout: float):
        try:
            line = self.lines.get(timeout=timeout)
        except queue.Empty:
            return None, "TIMEOUT"
        if line is None:
            return None, f"the mcporter runtime exited ({self._stderr_tail() or 'no stderr'})"
        try:
            return json.loads(line), None
        except ValueError:
            return None, f"the mcporter runtime printed a line that is not JSON: {line[:200]}"

    def _start(self) -> str | None:
        self.p = subprocess.Popen(["node", self.helper], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        self.lines, self.errors = queue.Queue(), queue.Queue()
        threading.Thread(target=self._pump, args=(self.p.stdout, self.lines), daemon=True).start()
        threading.Thread(target=self._pump, args=(self.p.stderr, self.errors), daemon=True).start()
        ready, err = self._line(120)
        if ready is None or not ready.get("ready"):
            why = err or str((ready or {}).get("error"))
            self.stop()
            return f"the mcporter runtime did not start: {why}"[:400]
        return None

    def stop(self) -> None:
        if self.p is not None:
            self.p.kill()
        self.p = None

    def send(self, tool: str, args: dict, timeout: float) -> tuple[str, str]:
        """-> (stdout text, stderr text) as the CLI process would give them. Raises TimeoutError on a timeout."""
        if self.p is None or self.p.poll() is not None:
            err = self._start()
            if err:
                return "", err
        self.n += 1
        request = {"id": self.n, "tool": tool, "args": args, "timeoutMs": int(timeout * 1000)}
        try:
            self.p.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
            self.p.stdin.flush()
        except OSError as exc:
            self.stop()
            return "", f"the mcporter runtime's stdin closed ({type(exc).__name__}): {self._stderr_tail()}"[:400]
        sent = self.n
        answer, err = self._line(timeout + 10)          # the helper enforces `timeoutMs` itself first
        if answer is None:
            self.stop()
            if err == "TIMEOUT":
                raise TimeoutError(f"{tool}: no answer in {timeout} s")
            return "", err
        if answer.get("id") != sent:
            self.stop()
            return "", f"the mcporter runtime answered call {answer.get('id')}, not {sent}"
        if not answer.get("ok"):
            return "", str(answer.get("error"))[:400]
        return json.dumps(answer.get("value")), ""


RUNTIME = Runtime()
atexit.register(RUNTIME.stop)          # the helper is a child process: it does not outlive the script
