import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable, Any, List
import threading

@dataclass
class SearchJob:
    """Represents a search job with query, timeout, and result future."""
    query: str
    max_wait_seconds: int
    future: asyncio.Future

@dataclass
class Worker:
    """Represents a worker with its own driver, queue, and state."""
    id: int
    driver: Any  # Chrome driver instance
    queue: asyncio.Queue[SearchJob]
    state: str  # ready|busy|stopped
    lock: threading.Lock

class JobRouter:
    """Routes jobs round-robin to N persistent workers."""
    
    def __init__(self, workers: List[Worker]):
        self.workers = workers
        self._next_idx = 0
        self.worker_tasks: List[asyncio.Task] = []
        
    async def start(self, process_fn: Callable[[Worker, SearchJob], Awaitable[Any]]):
        """Start all worker loops with the given processing function."""
        # Stop any existing tasks
        await self.stop()
        
        # Start worker loops
        for worker in self.workers:
            task = asyncio.create_task(self._worker_loop(worker, process_fn))
            self.worker_tasks.append(task)
            
    async def _worker_loop(self, worker: Worker, process_fn: Callable[[Worker, SearchJob], Awaitable[Any]]):
        """Background worker loop that processes jobs for a specific worker."""
        worker.state = "ready"
        print(f"✅ Worker {worker.id} ready - accepting jobs")
        
        while True:
            try:
                # Wait for next job
                job = await worker.queue.get()
                
                # Process the job
                worker.state = "busy"
                print(f"Worker {worker.id} processing job: {job.query}")
                
                try:
                    result = await process_fn(worker, job)
                    job.future.set_result(result)
                except Exception as e:
                    job.future.set_exception(e)
                finally:
                    worker.queue.task_done()
                    worker.state = "ready"
                    print(f"Worker {worker.id} completed job, ready for next")
                    
            except asyncio.CancelledError:
                worker.state = "stopped"
                print(f"Worker {worker.id} stopped")
                break
            except Exception as e:
                print(f"Worker {worker.id} error: {e}")
                continue
                
    async def enqueue(self, query: str, max_wait_seconds: int) -> Any:
        """Enqueue a job using round-robin selection with idle preference."""
        future = asyncio.Future()
        job = SearchJob(query=query, max_wait_seconds=max_wait_seconds, future=future)
        
        # Try to find an idle worker starting from next_idx
        selected_worker = None
        for i in range(len(self.workers)):
            idx = (self._next_idx + i) % len(self.workers)
            worker = self.workers[idx]
            if worker.state == "ready":
                selected_worker = worker
                self._next_idx = (idx + 1) % len(self.workers)
                break
        
        # If no idle worker found, use round-robin anyway
        if selected_worker is None:
            selected_worker = self.workers[self._next_idx]
            self._next_idx = (self._next_idx + 1) % len(self.workers)
        
        await selected_worker.queue.put(job)
        print(f"Job enqueued to worker {selected_worker.id}: {query}")
        
        return await future
        
    async def stop(self):
        """Stop all worker tasks gracefully."""
        for task in self.worker_tasks:
            if not task.done():
                task.cancel()
                
        # Wait for all tasks to complete
        if self.worker_tasks:
            try:
                await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            except Exception:
                pass
                
        self.worker_tasks.clear()
        
    def get_states(self) -> List[str]:
        """Get current states of all workers."""
        return [worker.state for worker in self.workers]
        
    def total_queue_size(self) -> int:
        """Get total queue size across all workers."""
        return sum(worker.queue.qsize() for worker in self.workers)
