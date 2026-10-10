"""Punto de entrada de Auto Cuadre: pantalla de carga -> actualización -> revisión de cuadres -> ventana principal."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from tasks import run_in_background
from ui_helpers import BG, MUTED, TEXT, apply_theme
from version import __version__

SKIP_UPDATE_ENV = "AUTOCUADRE_JUST_UPDATED"  # evita un bucle si el paquete no sube la versión


class Splash(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg=BG)
        width, height = 460, 210
        self.geometry(f"{width}x{height}+{(self.winfo_screenwidth() - width) // 2}+{(self.winfo_screenheight() - height) // 3}")
        apply_theme(self)
        tk.Label(self, text="Auto Cuadre", bg=BG, fg=TEXT, font=("Segoe UI", 20, "bold")).pack(pady=(34, 2))
        tk.Label(self, text=f"Versión {__version__}", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack()
        self.value = tk.DoubleVar(value=0)
        self.text = tk.StringVar(value="Iniciando…")
        ttk.Progressbar(self, style="Auto.Horizontal.TProgressbar", variable=self.value, maximum=100).pack(fill="x", padx=40, pady=(24, 6))
        tk.Label(self, textvariable=self.text, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack()
        self.update_idletasks()

    def progress(self, fraction: float, text: str, _data=None) -> None:
        self.value.set(max(0.0, min(fraction, 1.0)) * 100)
        self.text.set(text)


def startup_work(report, cancel) -> dict:
    """Corre en segundo plano: instala actualización (si hay) y revisa cuadres faltantes."""
    from cuadre_checker import find_missing_cuadres
    from updater import apply_package, check_for_update, consume_update_notice, download_package
    from utils import ConfigurationError, load_config

    result: dict = {"updated": consume_update_notice()}
    try:
        config = load_config()
    except ConfigurationError as error:
        result["warning"] = str(error)
        return result

    if not os.environ.get(SKIP_UPDATE_ENV):
        try:
            report(0.05, "Buscando actualizaciones…")
            info = check_for_update(config.get("update_manifest_url", ""))
            if info:
                report(0.10, f"Nueva versión {info['version']} disponible")
                package = download_package(info, lambda fraction, text: report(0.10 + fraction * 0.60, text))
                report(0.75, "Instalando actualización…")
                apply_package(package, info)
                result["restart"] = True
                report(1.0, "Actualización instalada. Reiniciando…")
                return result
        except Exception as error:  # sin red / manifiesto roto: se continúa con la versión actual
            result["update_error"] = str(error)

    report(0.85, "Revisando cuadres del mes…")
    try:
        result["missing"] = find_missing_cuadres(config)
    except Exception as error:
        result["warning"] = str(error)
    report(1.0, "Listo")
    return result


def main() -> None:
    splash = Splash()
    result: dict = {}

    def finish(data=None) -> None:
        result.update(data or {})
        splash.quit()

    run_in_background(splash, startup_work, on_progress=splash.progress, on_done=finish,
                      on_error=lambda error: finish({"warning": f"Error al iniciar: {error}"}))
    splash.mainloop()
    splash.destroy()

    if result.get("restart"):
        from updater import restart_application
        os.environ[SKIP_UPDATE_ENV] = "1"
        restart_application()
        return

    from app_auto_cuadre import AutoCuadreShell
    AutoCuadreShell(result).mainloop()


if __name__ == "__main__":
    main()
