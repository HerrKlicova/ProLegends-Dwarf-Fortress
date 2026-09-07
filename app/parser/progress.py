"""Barra de progreso de consola. Sin dependencias externas."""

from __future__ import annotations

import shutil
import sys
import time


class ConsoleProgress:
    def __init__(self, label: str, total: int, enabled: bool = True) -> None:
        self.label = label
        self.total = max(1, total)
        self.enabled = enabled and sys.stdout is not None
        self.start = time.time()
        self._last = 0.0
        self._done = False

    def update(self, current: int, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.time()
        if not force and now - self._last < 0.15:
            return
        self._last = now
        frac = min(1.0, current / self.total)
        width = max(20, min(46, shutil.get_terminal_size((90, 20)).columns - 44))
        filled = int(width * frac)
        bar = "#" * filled + "-" * (width - filled)
        mb = current / (1024 * 1024)
        total_mb = self.total / (1024 * 1024)
        elapsed = now - self.start
        eta = (elapsed / frac - elapsed) if frac > 0.02 else 0.0
        sys.stdout.write(
            f"\r  {self.label:<22} [{bar}] {frac*100:5.1f}%  "
            f"{mb:6.1f}/{total_mb:.1f} MB  ETA {eta:4.0f}s"
        )
        sys.stdout.flush()

    def finish(self, note: str = "") -> None:
        if not self.enabled or self._done:
            return
        self._done = True
        self.update(self.total, force=True)
        elapsed = time.time() - self.start
        sys.stdout.write(f"  hecho en {elapsed:.1f}s{(' - ' + note) if note else ''}\n")
        sys.stdout.flush()
