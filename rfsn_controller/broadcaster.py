"""RFSN Progress Broadcaster.

Sends real-time events to the local dashboard via HTTP.
Fire-and-forget architecture to avoid blocking the controller.
"""

import threading
import requests
import queue
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Default dashboard URL
DASHBOARD_URL = "http://localhost:8000/api/events"

@dataclass
class Event:
    type: str
    data: Dict[str, Any]
    run_id: Optional[str] = None

class ProgressBroadcaster:
    """Async event broadcaster for the dashboard."""
    
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id
        self._queue: queue.Queue[Event] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        self.enabled = True

    def log(self, message: str, level: str = "info"):
        """Broadcast a log message."""
        self._enqueue("log", {"message": message, "level": level})

    def status(self, phase: str, step: Optional[int] = None, max_steps: Optional[int] = None):
        """Broadcast status update."""
        data = {"phase": phase}
        if step is not None:
            data["step"] = step
        if max_steps is not None:
            data["max_steps"] = max_steps
        self._enqueue("status", data)

    def metric(self, patches_tried: int, success_rate: float, cost_est: float):
        """Broadcast metrics."""
        self._enqueue("metric", {
            "patches_tried": patches_tried,
            "success_rate": round(success_rate, 1),
            "cost_est": cost_est
        })

    def _enqueue(self, type: str, data: Dict[str, Any]):
        if not self.enabled:
            return
        self._queue.put(Event(type=type, data=data, run_id=self.run_id))

    def _worker(self):
        """Background worker to send requests."""
        while not self._stop_event.is_set():
            try:
                # Batch events if possible, but simplicity first
                event = self._queue.get(timeout=0.5)
                try:
                    requests.post(
                        DASHBOARD_URL, 
                        json=asdict(event),
                        timeout=0.2 # Fast timeout, don't block
                    )
                except requests.RequestException:
                    # Dashboard probably not running, ignore
                    pass
                finally:
                    self._queue.task_done()
            except queue.Empty:
                continue

    def close(self):
        """Stop the worker."""
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
