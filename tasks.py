"""Tareas en segundo plano para Tkinter: el trabajo pesado corre en un hilo y los resultados
vuelven al hilo de la interfaz mediante `after`, de modo que la ventana nunca se congela."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Any, Callable

WorkFn = Callable[[Callable[..., None], threading.Event], Any]


class BackgroundTask:
    def __init__(self, widget, work: WorkFn, on_progress=None, on_done=None, on_error=None) -> None:
        self.widget, self.work = widget, work
        self.on_progress, self.on_done, self.on_error = on_progress, on_done, on_error
        self.cancel_event = threading.Event()
        self.queue: queue.Queue = queue.Queue()
        self.active = True
        threading.Thread(target=self._run, daemon=True).start()
        self._poll()

    def cancel(self, silent: bool = False) -> None:
        """Pide detener el trabajo. silent=True además descarta sus callbacks (otra tarea la reemplaza)."""
        self.cancel_event.set()
        if silent:
            self.active = False

    def _report(self, fraction: float, text: str = "", data: Any = None) -> None:
        self.queue.put(("progress", (fraction, text, data)))

    def _run(self) -> None:
        try:
            self.queue.put(("done", self.work(self._report, self.cancel_event)))
        except BaseException as error:  # noqa: BLE001 - se reenvía al hilo de la interfaz
            self.queue.put(("error", error))

    def _poll(self) -> None:
        try:
            while self.active:
                kind, payload = self.queue.get_nowait()
                if kind == "progress":
                    if self.on_progress:
                        self.on_progress(*payload)
                elif kind == "done":
                    self.active = False
                    if self.on_done:
                        self.on_done(payload)
                else:
                    self.active = False
                    if self.on_error:
                        self.on_error(payload)
        except queue.Empty:
            pass
        except tk.TclError:  # la ventana se cerró
            self.active = False
            return
        if self.active:
            try:
                self.widget.after(60, self._poll)
            except tk.TclError:
                self.active = False


def run_in_background(widget, work: WorkFn, *, on_progress=None, on_done=None, on_error=None) -> BackgroundTask:
    """work(report, cancel) -> resultado. report(fracción, texto, datos) envía avance a on_progress."""
    return BackgroundTask(widget, work, on_progress, on_done, on_error)
