"""Bounded, non-preemptive queue with limited preference for short dictation.

The oldest waiting job can be bypassed at most twice and cannot be bypassed
after 30 seconds. No running inference is interrupted or duplicated.
"""
import asyncio
import time


class InferenceQueue(asyncio.Queue):
    def __init__(self, maxsize=8, *, is_short, clock=time.monotonic):
        self.is_short = is_short
        self.clock = clock
        self.bypasses = 0
        super().__init__(maxsize=maxsize)

    def _init(self, maxsize):
        self._queue = []

    def _put(self, item):
        self._queue.append((self.clock(), self.is_short(item), item))

    def _get(self):
        oldest_time, oldest_short, _ = self._queue[0]
        index = 0
        if not oldest_short and self.bypasses < 2 and self.clock() - oldest_time < 30:
            index = next((i for i, (_, short, _) in enumerate(self._queue) if short), 0)
        if index:
            self.bypasses += 1
        else:
            self.bypasses = 0
        return self._queue.pop(index)[2]
