import asyncio
import unittest

from inference_queue import InferenceQueue


class QueueTests(unittest.IsolatedAsyncioTestCase):
    def make_queue(self, clock=lambda: 0):
        return InferenceQueue(maxsize=8, is_short=lambda item: item.startswith('short'), clock=clock)

    async def test_short_work_moves_ahead_without_reordering_peers(self):
        queue = self.make_queue()
        for item in ('long-a', 'long-b', 'short-a', 'short-b'):
            queue.put_nowait(item)
        self.assertEqual([queue.get_nowait() for _ in range(4)],
                         ['short-a', 'short-b', 'long-a', 'long-b'])
        for _ in range(4):queue.task_done()
        await asyncio.wait_for(queue.join(), 1)

    async def test_continually_arriving_short_jobs_cannot_starve_oldest(self):
        queue = self.make_queue()
        queue.put_nowait('long-a')
        for i in range(2):
            queue.put_nowait(f'short-{i}')
            self.assertEqual(queue.get_nowait(), f'short-{i}')
            queue.task_done()
        queue.put_nowait('short-new')
        self.assertEqual(queue.get_nowait(), 'long-a')
        queue.task_done()
        self.assertEqual(queue.get_nowait(), 'short-new')
        queue.task_done()
        await queue.join()

    async def test_oldest_at_thirty_seconds_is_no_longer_bypassed(self):
        now = [0]
        queue = self.make_queue(clock=lambda: now[0])
        queue.put_nowait('long-a')
        now[0] = 30
        queue.put_nowait('short-new')
        self.assertEqual(queue.get_nowait(), 'long-a')
        self.assertEqual(queue.get_nowait(), 'short-new')

    async def test_bound_and_waiters_keep_asyncio_semantics(self):
        queue = self.make_queue()
        for i in range(8):queue.put_nowait(f'long-{i}')
        with self.assertRaises(asyncio.QueueFull):queue.put_nowait('short-overflow')
        blocked = asyncio.create_task(queue.put('short-later'))
        await asyncio.sleep(0)
        self.assertFalse(blocked.done())
        self.assertEqual(await queue.get(), 'long-0')
        queue.task_done()
        await asyncio.wait_for(blocked, 1)
        self.assertEqual(await queue.get(), 'short-later')
        queue.task_done()
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()
        await asyncio.wait_for(queue.join(), 1)


if __name__ == '__main__':
    unittest.main()
