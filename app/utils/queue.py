import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable, Any

@dataclass
class SearchJob:
    """Represents a search job with query, timeout, and result future."""
    query: str
    max_wait_seconds: int
    future: asyncio.Future

class JobQueue:
    """FIFO job queue with background worker for processing search requests."""
    
    def __init__(self):
        self.queue: asyncio.Queue[SearchJob] = asyncio.Queue()
        self.worker_task: asyncio.Task = None
        self.state: str = "initializing"  # initializing|ready|busy|stopped
        
    async def start(self, process_fn: Callable[[SearchJob], Awaitable[Any]]):
        """Start the background worker with the given processing function."""
        if self.worker_task and not self.worker_task.done():
            return
            
        self.worker_task = asyncio.create_task(self._worker_loop(process_fn))
        
    async def _worker_loop(self, process_fn: Callable[[SearchJob], Awaitable[Any]]):
        """Background worker loop that processes jobs FIFO."""
        self.state = "ready"
        print("✅ Queue worker ready - accepting jobs")
        
        while True:
            try:
                # Wait for next job
                job = await self.queue.get()
                
                # Process the job
                self.state = "busy"
                print(f"Processing job: {job.query}")
                
                try:
                    result = await process_fn(job)
                    job.future.set_result(result)
                except Exception as e:
                    job.future.set_exception(e)
                finally:
                    self.queue.task_done()
                    self.state = "ready"
                    print("Job completed, worker ready for next job")
                    
            except asyncio.CancelledError:
                self.state = "stopped"
                print("Queue worker stopped")
                break
            except Exception as e:
                print(f"Worker error: {e}")
                continue
                
    async def enqueue(self, query: str, max_wait_seconds: int) -> Any:
        """Enqueue a job and return awaitable future for the result."""
        future = asyncio.Future()
        job = SearchJob(query=query, max_wait_seconds=max_wait_seconds, future=future)
        
        await self.queue.put(job)
        print(f"Job enqueued: {query}")
        
        return await future
        
    async def stop(self):
        """Stop the background worker gracefully."""
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
                
    def get_state(self) -> str:
        """Get current worker state."""
        return self.state
        
    def size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
