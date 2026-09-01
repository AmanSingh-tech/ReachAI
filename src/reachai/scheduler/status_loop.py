from __future__ import annotations

import time
from typing import Any, Dict


class StatusLoop:
    def __init__(self, poll_seconds: int = 600):
        self.poll_seconds = poll_seconds

    def run(self, on_tick) -> Dict[str, Any]:
        while True:
            tick = on_tick()
            if tick.get("stop"):
                return tick
            time.sleep(self.poll_seconds)
