"""Nested inference deadlines, not per-packet HTTP idle timeouts.

The local provider must outlive decoder admission (17s), GPU admission (5s),
speech including cold start (60s plus up to 10s reaping), and formatting (90s).
The queue's outer budget retains room for transport cleanup and failure state.
"""
import asyncio

SPEECH_SECONDS = 60
FORMAT_SECONDS = 90
LOCAL_PROVIDER_SECONDS = 190
QUEUED_JOB_SECONDS = 240


async def format_before_deadline(formatter, *args):
    # Includes every translation bridge and optional layout call, not 90s each.
    async with asyncio.timeout(FORMAT_SECONDS):
        return await formatter(*args)
