"""A tiny in-process background worker that delivers order notifications."""
import queue
import threading


class WorkerUnavailable(Exception):
    pass


class NotificationWorker:
    def __init__(self) -> None:
        self.jobs: queue.Queue = queue.Queue()
        self.delivered: list[dict] = []
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="notification-worker", daemon=True)
        self._thread.start()

    def submit(self, event: dict) -> None:
        if not (self._thread and self._thread.is_alive()):
            raise WorkerUnavailable("notification worker is not running")
        self.jobs.put(event)

    def drain(self) -> None:
        self.jobs.join()

    def _run(self) -> None:
        while True:
            event = self.jobs.get()
            self.delivered.append(event)
            self.jobs.task_done()


worker = NotificationWorker()
