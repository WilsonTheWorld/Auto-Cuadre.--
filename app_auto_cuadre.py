"""Ventana principal de Auto Cuadre.

Una sola ventana: el contenido cambia dinámicamente entre vistas (Inicio, Cuadre del día,
Estadísticas, Configuración) en lugar de abrir ventanas nuevas.
"""

from __future__ import annotations

from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox

from app_cuadre_digital import AutoCuadreApp
from cuadre_checker import find_missing_cuadres, format_day
from tasks import run_in_background
from ui_helpers import (AMBER, BG, BORDER, BTN, CYAN, GREEN, MUTED, PURPLE, RED, SURFACE,
                        SURFACE_ALT, TEXT, apply_theme, fit_window, flat_button, money,
                        spanish_date, to_number)
from utils import (ConfigurationError, ensure_daily_workbook, load_config, open_with_system,
                   read_daily_values)
from version import __version__
from view_settings import SettingsView
from view_statistics import StatisticsView


class HomeView(tk.Frame):
    """Panel de control: tarjetas de acceso, resumen del cuadre de hoy y avisos."""

    def __init__(self, master, shell: "AutoCuadreShell") -> None:
        super().__init__(master, bg=BG)
        self.shell = shell
        self.balance_var = tk.StringVar(value="$ —")
        self.cash_var = tk.StringVar(value="$ —")
        self.state_var = tk.StringVar(value="Cargando estado")
        self.detail_var = tk.StringVar(value="Consultando el cuadre del día...")
        self.alert_title = tk.StringVar()
        self.alert_body = tk.StringVar()
        self._build()
        self.render_alerts()
        self.refresh_today()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)

        # Aviso de cuadres faltantes (oculto si no hay nada que avisar)
        self.alert_wrapper = tk.Frame(self, bg=BG, padx=30)
        self.alert_wrapper.columnconfigure(0, weight=1)
        self.alert = tk.Frame(self.alert_wrapper, bg="#2E250A", highlightbackground=AMBER, highlightthickness=1, padx=16, pady=11)
        self.alert.grid(row=0, column=0, sticky="ew")
        self.alert.columnconfigure(0, weight=1)
        tk.Label(self.alert, textvariable=self.alert_title, bg="#2E250A", fg=AMBER, font=("Segoe UI", 10, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(self.alert, textvariable=self.alert_body, bg="#2E250A", fg=TEXT, font=("Segoe UI", 9),
                 justify="left", anchor="w", wraplength=720).grid(row=1, column=0, sticky="w", pady=(3, 0))
        flat_button(self.alert, "Revisar de nuevo", self.shell.recheck_missing, secondary=True).grid(row=0, column=1, rowspan=2, padx=(12, 0))

        main = tk.Frame(self, bg=BG, padx=30)
        main.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)
        tk.Label(main, text="Panel de control", bg=BG, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(14, 0))
        tk.Label(main, text="Seleccione una opción para continuar con el cuadre de hoy.", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 16))

        cards = tk.Frame(main, bg=BG)
        cards.pack(fill="x")
        for column in range(3):
            cards.columnconfigure(column, weight=1, uniform="card")
        self._card(cards, 0, "01", "Cuadre del día", "Registre ingresos, recibos y efectivo de hoy.",
                   PURPLE, "Abrir captura", lambda: self.shell.show("capture"))
        self._card(cards, 1, "02", "Estadísticas", "Compare balances, efectivo y diferencias por período.",
                   CYAN, "Ver estadísticas", lambda: self.shell.show("stats"))
        self._card(cards, 2, "03", "Lanzar cuadre actual", "Abra el archivo Excel del día para revisión manual.",
                   GREEN, "Abrir en Excel", self.open_current_workbook)

        summary = tk.Frame(main, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=19, pady=16)
        summary.pack(fill="x", pady=(18, 0))
        summary.columnconfigure(1, weight=1)
        tk.Label(summary, text="Resumen del cuadre actual", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(summary, text="Balance del día", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(13, 1))
        tk.Label(summary, textvariable=self.balance_var, bg=SURFACE, fg=TEXT, font=("Segoe UI", 17, "bold")).grid(row=2, column=0, sticky="w")
        tk.Label(summary, text="Efectivo en caja", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", padx=(42, 0), pady=(13, 1))
        tk.Label(summary, textvariable=self.cash_var, bg=SURFACE, fg=TEXT, font=("Segoe UI", 17, "bold")).grid(row=2, column=1, sticky="w", padx=(42, 0))
        self.state_badge = tk.Label(summary, textvariable=self.state_var, bg="#27203F", fg=MUTED,
                                    font=("Segoe UI", 10, "bold"), padx=11, pady=6)
        self.state_badge.grid(row=1, column=2, rowspan=2, sticky="e", padx=(25, 10))
        tk.Label(summary, textvariable=self.detail_var, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
                 justify="right", wraplength=230).grid(row=1, column=3, rowspan=2, sticky="e")

        footer = tk.Frame(self, bg=BG, padx=30, pady=16)
        footer.grid(row=2, column=0, sticky="ew")
        flat_button(footer, "Imprimir cuadre actual", self.show_print_menu, secondary=True).pack(side="left")
        flat_button(footer, "Actualizar panel", self.shell.refresh_home, secondary=True).pack(side="right")

    def _card(self, parent, column: int, number: str, title: str, description: str, color: str,
              action: str, command) -> None:
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=18, cursor="hand2")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 2 else 8))
        top = tk.Frame(card, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=number, bg=color, fg=BG, font=("Segoe UI", 10, "bold"), padx=8, pady=5).pack(side="left")
        tk.Label(top, text="●", bg=SURFACE, fg=color, font=("Segoe UI", 13)).pack(side="right")
        tk.Label(card, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(20, 5))
        tk.Label(card, text=description, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), justify="left",
                 wraplength=200).pack(anchor="w")
        flat_button(card, action, command, accent=color).pack(anchor="w", pady=(20, 0))
        for widget in (card, top):
            widget.bind("<Button-1>", lambda _event, callback=command: callback())

    # ------------------------------------------------------------------ avisos
    def on_show(self) -> None:
        self.render_alerts()

    def render_alerts(self) -> None:
        missing, warning = self.shell.missing, self.shell.check_warning
        if missing:
            shown = [format_day(day) for day in missing[:10]]
            more = f" y {len(missing) - 10} más" if len(missing) > 10 else ""
            self.alert_title.set(f"Cuadres pendientes del mes: {len(missing)}")
            self.alert_body.set("No hay cuadre registrado para: " + "; ".join(shown) + more + ".")
        elif warning:
            self.alert_title.set("No se pudieron verificar los cuadres del mes")
            self.alert_body.set(warning)
        else:
            self.alert_wrapper.grid_remove()
            return
        self.alert_wrapper.grid(row=0, column=0, sticky="ew", pady=(14, 0))

    # ------------------------------------------------------------------ resumen de hoy
    def refresh_today(self) -> None:
        self.state_var.set("ACTUALIZANDO")
        self.detail_var.set("Leyendo el archivo actual de Excel...")
        run_in_background(self, lambda report, cancel: read_daily_values(load_config()),
                          on_done=self._apply_today, on_error=self._apply_today_error)

    def _apply_today(self, values) -> None:
        if not values:
            self.balance_var.set("$ —")
            self.cash_var.set("$ —")
            self.state_var.set("SIN REGISTRO")
            self.detail_var.set("Todavía no existe un cuadre guardado para hoy.")
            self.state_badge.configure(bg="#27203F", fg=MUTED)
            return
        balance, cash = to_number(values.get("balance")), to_number(values.get("cash"))
        self.balance_var.set(money(balance))
        self.cash_var.set(money(cash))
        if balance is None or cash is None:
            self.state_var.set("PENDIENTE")
            self.detail_var.set("Faltan valores para calcular el estado.")
            self.state_badge.configure(bg="#27203F", fg=MUTED)
            return
        delta = cash - balance
        if abs(delta) < 0.005:
            self.state_var.set("CUADRADO")
            self.detail_var.set("El efectivo coincide con el balance del día.")
            self.state_badge.configure(bg="#123F3B", fg=GREEN)
        elif delta > 0:
            self.state_var.set("SOBRANTE")
            self.detail_var.set(f"Sobrante: {money(delta)}")
            self.state_badge.configure(bg="#44350F", fg=AMBER)
        else:
            self.state_var.set("FALTANTE")
            self.detail_var.set(f"Faltante: {money(abs(delta))}")
            self.state_badge.configure(bg="#481C31", fg=RED)

    def _apply_today_error(self, error: BaseException) -> None:
        self.state_var.set("REVISAR EXCEL")
        self.detail_var.set(str(error))
        self.state_badge.configure(bg="#481C31", fg=RED)

    # ------------------------------------------------------------------ acciones
    def open_current_workbook(self) -> None:
        try:
            open_with_system(ensure_daily_workbook(load_config()))
        except Exception as error:
            messagebox.showerror("Auto Cuadre", f"No se pudo abrir el cuadre actual:\n{error}", parent=self.winfo_toplevel())

    def show_print_menu(self) -> None:
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title("Imprimir cuadre actual")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        body = tk.Frame(dialog, bg=SURFACE, padx=22, pady=20)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(body, text="Imprimir cuadre actual", bg=SURFACE, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text="Abra Excel para elegir impresora y ajustes, o imprima directamente en la impresora predeterminada.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), wraplength=400, justify="left").pack(anchor="w", pady=(6, 16))
        flat_button(body, "Abrir en Excel para imprimir", lambda: self._open_for_print(dialog), accent=PURPLE).pack(fill="x", pady=3)
        flat_button(body, "Imprimir en impresora predeterminada", lambda: self._print_default(dialog), secondary=True).pack(fill="x", pady=3)
        flat_button(body, "Cancelar", dialog.destroy, secondary=True).pack(anchor="e", pady=(12, 0))

    def _open_for_print(self, dialog: tk.Toplevel) -> None:
        try:
            open_with_system(ensure_daily_workbook(load_config()))
            dialog.destroy()
        except Exception as error:
            messagebox.showerror("Imprimir", str(error), parent=dialog)

    def _print_default(self, dialog: tk.Toplevel) -> None:
        if not messagebox.askyesno("Imprimir", "Se enviará el cuadre actual a la impresora predeterminada. ¿Desea continuar?", parent=dialog):
            return
        try:
            open_with_system(ensure_daily_workbook(load_config()), "print")
            dialog.destroy()
        except Exception as error:
            messagebox.showerror("Imprimir", str(error), parent=dialog)


class AutoCuadreShell(tk.Tk):
    """Marco de la aplicación: cabecera con navegación + área de contenido intercambiable."""

    NAV = (("home", "Inicio"), ("capture", "Cuadre del día"), ("stats", "Estadísticas"), ("settings", "Configuración"))

    def __init__(self, startup: dict | None = None) -> None:
        super().__init__()
        self.startup = startup or {}
        self.missing: list[date] = list(self.startup.get("missing", []))
        self.check_warning: str = self.startup.get("warning", "")
        self.title(f"Auto Cuadre {__version__}")
        self.configure(bg=BG)
        fit_window(self, 1180, 730, 860, 520)
        apply_theme(self)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self.views: dict[str, tk.Misc] = {}
        self.nav_buttons: dict[str, tk.Button] = {}
        self._build_header()
        self.content = tk.Frame(self, bg=BG)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.show("home")
        self.after(400, self._startup_notices)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG, padx=24, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="AUTO", bg=PURPLE, fg="white", font=("Segoe UI", 10, "bold"), padx=10, pady=5).pack(side="left")
        tk.Label(header, text="Auto Cuadre", bg=BG, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(side="left", padx=(10, 18))
        for key, label in self.NAV:
            button = tk.Button(header, text=label, command=lambda value=key: self.show(value), relief="flat", bd=0,
                               font=("Segoe UI", 9, "bold"), padx=12, pady=6, cursor="hand2", bg=BTN, fg=TEXT,
                               activebackground=PURPLE, activeforeground=BG)
            button.pack(side="left", padx=(0, 6))
            self.nav_buttons[key] = button
        tk.Label(header, text=spanish_date(datetime.now().date()), bg=SURFACE_ALT, fg=TEXT,
                 font=("Segoe UI", 9, "bold"), padx=12, pady=6).pack(side="right")

    # ------------------------------------------------------------------ navegación
    def _make_view(self, name: str) -> tk.Misc:
        if name == "home":
            return HomeView(self.content, self)
        if name == "capture":
            return AutoCuadreApp(self.content, embedded=True, on_saved=self.on_cuadre_saved)
        if name == "stats":
            return StatisticsView(self.content, self)
        return SettingsView(self.content, self)

    def show(self, name: str) -> None:
        view = self.views.get(name)
        if view is None:  # las vistas se crean la primera vez que se visitan
            view = self.views[name] = self._make_view(name)
            view.grid(row=0, column=0, sticky="nsew")
        view.tkraise()
        for key, button in self.nav_buttons.items():
            active = key == name
            button.configure(bg=PURPLE if active else BTN, fg=BG if active else TEXT)
        if hasattr(view, "on_show"):
            view.on_show()

    # ------------------------------------------------------------------ eventos entre vistas
    def refresh_home(self) -> None:
        home = self.views.get("home")
        if home:
            home.refresh_today()
        self.recheck_missing()

    def recheck_missing(self) -> None:
        def work(report, cancel):
            return find_missing_cuadres(load_config())

        def done(missing):
            self.missing, self.check_warning = missing, ""
            self._render_home_alerts()

        def failed(error):
            self.missing = []
            self.check_warning = str(error) if isinstance(error, ConfigurationError) else f"No se pudo verificar: {error}"
            self._render_home_alerts()

        run_in_background(self, work, on_done=done, on_error=failed)

    def _render_home_alerts(self) -> None:
        home = self.views.get("home")
        if home:
            home.render_alerts()

    def on_cuadre_saved(self) -> None:
        self.refresh_home()

    def on_config_changed(self) -> None:
        stats = self.views.get("stats")
        if stats:
            stats.invalidate()
        self.refresh_home()

    def _startup_notices(self) -> None:
        updated = self.startup.get("updated")
        if updated:
            notes = f"\n\n{updated['notes']}" if updated.get("notes") else ""
            messagebox.showinfo("Auto Cuadre actualizado", f"Se instaló la versión {updated['version']}.{notes}", parent=self)
        if self.missing:
            lines = "\n".join(f"• {format_day(day)}" for day in self.missing[:12])
            more = f"\n… y {len(self.missing) - 12} más" if len(self.missing) > 12 else ""
            messagebox.showwarning("Cuadres pendientes", f"No hay cuadre registrado para:\n\n{lines}{more}", parent=self)


def main() -> None:
    AutoCuadreShell().mainloop()  # sin pantalla de carga (uso de desarrollo); el normal es main.py


if __name__ == "__main__":
    main()
