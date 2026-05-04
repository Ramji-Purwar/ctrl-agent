import queue
import threading
import logging

HIGH = 0
LOW  = 1

_queue   = queue.PriorityQueue()
_counter = 0
_lock    = threading.Lock()

def _worker():
    while True:
        priority, count, fn, args, kwargs, result_holder, done_event = _queue.get()
        try:
            result_holder["result"] = fn(*args, **kwargs)
        except Exception as e:
            result_holder["error"] = str(e)
            logging.error(f"[Queue][P{priority}] Task failed: {e}")
        finally:
            done_event.set()
            _queue.task_done()

threading.Thread(target=_worker, daemon=True).start()

def submit_task(fn, *args, priority: int = HIGH, timeout: int = 60, **kwargs) -> dict:
    global _counter
    result_holder = {}
    done_event    = threading.Event()

    with _lock:
        _counter += 1
        count = _counter

    _queue.put((priority, count, fn, args, kwargs, result_holder, done_event))

    completed = done_event.wait(timeout=timeout)
    if not completed:
        logging.error(f"[Queue] Task timed out after {timeout}s: {fn.__name__}")
        return {"error": f"Task timed out after {timeout}s"}

    return result_holder