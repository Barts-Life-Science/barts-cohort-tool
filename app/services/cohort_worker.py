import threading
import logging
import os

import persistqueue
from persistqueue.exceptions import Empty

from app.config import settings

logger = logging.getLogger(__name__)

_queue: persistqueue.SQLiteAckQueue | None = None
_stop_event = threading.Event()
_worker_threads: list[threading.Thread] = []


def get_queue() -> persistqueue.SQLiteAckQueue:
    if _queue is None:
        raise RuntimeError("Queue not initialised. start_workers() must be called first.")
    return _queue


def _worker_loop(worker_id: int) -> None:
    logger.info(f"[Worker-{worker_id}] started")

    while not _stop_event.is_set():
        try:
            item = _queue.get(block=True, timeout=2.0)
        except Empty:
            continue
        except Exception as e:
            logger.error(f"[Worker-{worker_id}] queue.get() error: {e}")
            continue

        # Deferred import to avoid circular dependency:
        # cohort_route imports settings; cohort_worker imports cohort_route here only at call time.
        from app.routes.cohort_route import CohortDefinition, process_cohort
        try:
            cohort = CohortDefinition.model_validate(item)
            logger.info(f"[Worker-{worker_id}] processing: {cohort.title!r}")
            process_cohort(cohort)
            _queue.ack(item)
            logger.info(f"[Worker-{worker_id}] complete: {cohort.title!r}")
        except Exception as e:
            logger.exception(f"[Worker-{worker_id}] job failed: {e}")
            _queue.nack(item)  # returns item to 'ready' for retry

    logger.info(f"[Worker-{worker_id}] stopped")
    
    
def initialise_queue(auto_resume=False):
    global _queue

    if _queue is None:
        os.makedirs(settings.queue_data_path, exist_ok=True)

        _queue = persistqueue.SQLiteAckQueue(
            path=settings.queue_data_path,
            name="cohort_jobs",
            multithreading=True,
            auto_commit=True,
            auto_resume=auto_resume,
        )

    return _queue


def start_workers() -> None:
    global _stop_event, _worker_threads

    initialise_queue(auto_resume=True)

    _stop_event = threading.Event()

    _worker_threads = []

    for i in range(settings.worker_count):
        t = threading.Thread(
            target=_worker_loop,
            args=(i,),
            name=f"cohort-worker-{i}",
            daemon=True,
        )
        t.start()
        _worker_threads.append(t)

    print(
        f">>> Started {settings.worker_count} queue workers "
        f"in PID {os.getpid()}",
        flush=True
    )

def stop_workers() -> None:
    logger.info("Signalling cohort workers to stop...")
    _stop_event.set()

    for t in _worker_threads:
        t.join(timeout=60)
        if t.is_alive():
            logger.warning(f"{t.name} did not stop within 60s")

    logger.info("All cohort workers stopped.")
