"""Panel principal oscuro de Auto Cuadre."""

from __future__ import annotations

from datetime import datetime
from threading import Thread
import tkinter as tk
from tkinter import messagebox

from app_cuadre_digital import AutoCuadreApp
from utils import (ConfigurationError, ensure_daily_workbook, get_statistics,
                   load_config, open_with_system, read_daily_values)


class AutoCuadreDashboard(tk.Tk):
    BG = "#090814"
    SURFACE = "#121023"
    SURFACE_ALT = "#18142B"
    BORDER = "#2A2445"
    TEXT = "#F4F1FF"
    MUTED = "#A8A2C7"
    PURPLE = "#8B5CF6"
    CYAN = "#22D3EE"
    GREEN = "#2DD4BF"
    AMBER = "#FBBF24"
    RED = "#FB7185"

    def __init__(self) -> None:
        super().__init__()
        self.title("Auto Cuadre")
        self.geometry("1180x730")
        self.minsize(1020, 660)
        self.configure(bg=self.BG)
        self.balance_var = tk.StringVar(value="$ —")
        self.cash_var = tk.StringVar(value="$ —")
        self.state_var = tk.StringVar(value="Cargando estado")
        self.detail_var = tk.StringVar(value="Consultando el cuadre del día...")
        self._build()
        self.after(150, self.refresh_today)

    def _build(self) -> None:
        header = tk.Frame(self, bg=self.BG, padx=30, pady=22)
        header.pack(fill="x")
        tk.Label(header, text="AUTO", bg=self.PURPLE, fg="white", font=("Segoe UI", 11, "bold"), padx=12, pady=7).pack(side="left")
        brand = tk.Frame(header, bg=self.BG)
        brand.pack(side="left", padx=13)
        tk.Label(brand, text="Auto Cuadre", bg=self.BG, fg=self.TEXT, font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(brand, text="Control diario de caja", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(header, text=datetime.now().strftime("%A, %d de %B de %Y").capitalize(), bg=self.SURFACE_ALT, fg=self.TEXT, font=("Segoe UI", 10, "bold"), padx=15, pady=8).pack(side="right")

        main = tk.Frame(self, bg=self.BG, padx=30)
        main.pack(fill="both", expand=True)
        tk.Label(main, text="Panel de control", bg=self.BG, fg=self.TEXT, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(main, text="Seleccione una opción para continuar con el cuadre de hoy.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 18))

        cards = tk.Frame(main, bg=self.BG)
        cards.pack(fill="x")
        for column in range(3):
            cards.columnconfigure(column, weight=1, uniform="card")
        self._create_dashboard_card(cards, 0, "01", "Cuadre del día", "Registre ingresos, recibos y efectivo de hoy.", self.PURPLE, "Abrir captura", self.open_capture)
        self._create_dashboard_card(cards, 1, "02", "Estadísticas", "Compare balances, efectivo y diferencias por período.", self.CYAN, "Ver estadísticas", self.open_statistics)
        self._create_dashboard_card(cards, 2, "03", "Lanzar cuadre actual", "Abra el archivo Excel del día para revisión manual.", self.GREEN, "Abrir en Excel", self.open_current_workbook)

        summary = tk.Frame(main, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1, padx=19, pady=16)
        summary.pack(fill="x", pady=(20, 0))
        summary.columnconfigure(1, weight=1)
        tk.Label(summary, text="Resumen del cuadre actual", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(summary, text="Balance del día", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(13, 1))
        tk.Label(summary, textvariable=self.balance_var, bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 17, "bold")).grid(row=2, column=0, sticky="w")
        tk.Label(summary, text="Efectivo en caja", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", padx=(42, 0), pady=(13, 1))
        tk.Label(summary, textvariable=self.cash_var, bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 17, "bold")).grid(row=2, column=1, sticky="w", padx=(42, 0))
        self.state_badge = tk.Label(summary, textvariable=self.state_var, bg="#27203F", fg=self.MUTED, font=("Segoe UI", 10, "bold"), padx=11, pady=6)
        self.state_badge.grid(row=1, column=2, rowspan=2, sticky="e", padx=(25, 10))
        tk.Label(summary, textvariable=self.detail_var, bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9), justify="right", wraplength=250).grid(row=1, column=3, rowspan=2, sticky="e")

        footer = tk.Frame(self, bg=self.BG, padx=30, pady=20)
        footer.pack(fill="x")
        self._button(footer, "Configuración", self.open_configuration, secondary=True).pack(side="left")
        self._button(footer, "Imprimir cuadre actual", self.show_print_menu, secondary=True).pack(side="left", padx=(10, 0))
        self._button(footer, "Actualizar panel", self.refresh_today, secondary=True).pack(side="right")

    def _create_dashboard_card(self, parent: tk.Frame, column: int, number: str, title: str,
                               description: str, color: str, action: str, command) -> None:
        card = tk.Frame(parent, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1, padx=19, pady=19, cursor="hand2")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 9, 0 if column == 2 else 9))
        top = tk.Frame(card, bg=self.SURFACE)
        top.pack(fill="x")
        tk.Label(top, text=number, bg=color, fg=self.BG, font=("Segoe UI", 10, "bold"), padx=8, pady=5).pack(side="left")
        tk.Label(top, text="●", bg=self.SURFACE, fg=color, font=("Segoe UI", 13)).pack(side="right")
        tk.Label(card, text=title, bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(25, 5))
        tk.Label(card, text=description, bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9), justify="left", wraplength=270).pack(anchor="w")
        button = self._button(card, action, command, accent=color)
        button.pack(anchor="w", pady=(26, 0))
        for widget in (card, top):
            widget.bind("<Button-1>", lambda _event, callback=command: callback())

    def _button(self, parent, text: str, command, *, accent: str | None = None, secondary: bool = False) -> tk.Button:
        background = "#211C37" if secondary else (accent or self.PURPLE)
        foreground = self.TEXT if secondary else self.BG
        return tk.Button(parent, text=text, command=command, bg=background, fg=foreground,
                         activebackground="#312852" if secondary else accent, activeforeground=self.TEXT,
                         relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=13, pady=8, cursor="hand2")

    @staticmethod
    def _number(value) -> float | None:
        try:
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _money(value) -> str:
        number = AutoCuadreDashboard._number(value)
        return "$ —" if number is None else f"$ {number:,.2f}"

    def refresh_today(self) -> None:
        self.state_var.set("ACTUALIZANDO")
        self.detail_var.set("Leyendo el archivo actual de Excel...")
        Thread(target=self._load_today_worker, daemon=True).start()

    def _load_today_worker(self) -> None:
        try:
            values = read_daily_values(load_config())
            self.after(0, lambda: self._apply_today(values))
        except Exception as error:
            self.after(0, lambda: self._apply_today_error(error))

    def _apply_today(self, values) -> None:
        if not values:
            self.balance_var.set("$ —")
            self.cash_var.set("$ —")
            self.state_var.set("SIN REGISTRO")
            self.detail_var.set("Todavía no existe un cuadre guardado para hoy.")
            self.state_badge.configure(bg="#27203F", fg=self.MUTED)
            return
        balance = self._number(values.get("balance"))
        cash = self._number(values.get("cash"))
        self.balance_var.set(self._money(balance))
        self.cash_var.set(self._money(cash))
        if balance is None or cash is None:
            self.state_var.set("PENDIENTE")
            self.detail_var.set("Faltan valores para calcular el estado.")
            self.state_badge.configure(bg="#27203F", fg=self.MUTED)
            return
        delta = cash - balance
        if abs(delta) < 0.005:
            self.state_var.set("CUADRADO")
            self.detail_var.set("El efectivo coincide con el balance del día.")
            self.state_badge.configure(bg="#123F3B", fg=self.GREEN)
        elif delta > 0:
            self.state_var.set("SOBRANTE")
            self.detail_var.set(f"Sobrante: {self._money(delta)}")
            self.state_badge.configure(bg="#44350F", fg=self.AMBER)
        else:
            self.state_var.set("FALTANTE")
            self.detail_var.set(f"Faltante: {self._money(abs(delta))}")
            self.state_badge.configure(bg="#481C31", fg=self.RED)

    def _apply_today_error(self, error: Exception) -> None:
        self.state_var.set("REVISAR EXCEL")
        self.detail_var.set(str(error))
        self.state_badge.configure(bg="#481C31", fg=self.RED)

    def open_capture(self) -> None:
        window = tk.Toplevel(self)
        window.configure(bg=self.BG)
        AutoCuadreApp(window)

    def open_statistics(self) -> None:
        StatisticsWindow(self)

    def open_current_workbook(self) -> None:
        try:
            open_with_system(ensure_daily_workbook(load_config()))
        except Exception as error:
            messagebox.showerror("Auto Cuadre", f"No se pudo abrir el cuadre actual:\n{error}", parent=self)

    def open_configuration(self) -> None:
        config = load_config()
        dialog = tk.Toplevel(self)
        dialog.title("Configuración institucional")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        body = tk.Frame(dialog, bg=self.SURFACE, padx=22, pady=20)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(body, text="Configuración", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(body, text="Las rutas institucionales se mantienen protegidas. El tema oscuro es el predeterminado.", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9), wraplength=470, justify="left").pack(anchor="w", pady=(4, 17))
        self._setting_row(body, "Modelo de Excel", config["template_path"])
        self._setting_row(body, "Carpeta de cuadres", config["base_dir"])
        self._button(body, "Cerrar", dialog.destroy, secondary=True).pack(anchor="e", pady=(18, 0))

    def _setting_row(self, parent: tk.Frame, label: str, value: str) -> None:
        row = tk.Frame(parent, bg=self.SURFACE_ALT, padx=12, pady=9)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=self.SURFACE_ALT, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(row, text=value, bg=self.SURFACE_ALT, fg=self.TEXT, font=("Segoe UI", 9), wraplength=440, justify="left").pack(anchor="w", pady=(2, 0))

    def show_print_menu(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Imprimir cuadre actual")
        dialog.configure(bg=self.BG)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        body = tk.Frame(dialog, bg=self.SURFACE, padx=22, pady=20)
        body.pack(fill="both", expand=True, padx=1, pady=1)
        tk.Label(body, text="Imprimir cuadre actual", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text="Abra Excel para elegir impresora y ajustes, o imprima directamente en la impresora predeterminada.", bg=self.SURFACE, fg=self.MUTED, font=("Segoe UI", 9), wraplength=400, justify="left").pack(anchor="w", pady=(6, 16))
        self._button(body, "Abrir en Excel para imprimir", lambda: self._open_for_print(dialog), accent=self.PURPLE).pack(fill="x", pady=3)
        self._button(body, "Imprimir en impresora predeterminada", lambda: self._print_default(dialog), secondary=True).pack(fill="x", pady=3)
        self._button(body, "Cancelar", dialog.destroy, secondary=True).pack(anchor="e", pady=(12, 0))

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


class StatisticsWindow(tk.Toplevel):
    def __init__(self, parent: AutoCuadreDashboard) -> None:
        super().__init__(parent)
        self.parent = parent
        self.period = "week"
        self.records: list[dict] = []
        self.title("Auto Cuadre | Estadísticas")
        self.geometry("1000x670")
        self.minsize(850, 600)
        self.configure(bg=parent.BG)
        self.period_buttons: dict[str, tk.Button] = {}
        self.summary_var = tk.StringVar(value="Cargando estadísticas...")
        self._build()
        self.load_period("week")

    def _build(self) -> None:
        header = tk.Frame(self, bg=self.parent.BG, padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="Estadísticas", bg=self.parent.BG, fg=self.parent.TEXT, font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(header, text="Comparación de balance y efectivo", bg=self.parent.BG, fg=self.parent.MUTED, font=("Segoe UI", 9)).pack(side="left", padx=12, pady=(5, 0))
        tk.Button(header, text="Cerrar", command=self.destroy, bg="#211C37", fg=self.parent.TEXT, relief="flat", padx=11, pady=6).pack(side="right")
        controls = tk.Frame(self, bg=self.parent.BG, padx=24)
        controls.pack(fill="x")
        for key, label in (("week", "Semanal"), ("month", "Mensual"), ("year", "Anual")):
            button = tk.Button(controls, text=label, command=lambda value=key: self.load_period(value), relief="flat", padx=15, pady=7, font=("Segoe UI", 9, "bold"))
            button.pack(side="left", padx=(0, 8))
            self.period_buttons[key] = button
        tk.Label(controls, textvariable=self.summary_var, bg=self.parent.BG, fg=self.parent.MUTED, font=("Segoe UI", 9)).pack(side="right")
        metrics = tk.Frame(self, bg=self.parent.BG, padx=24, pady=18)
        metrics.pack(fill="x")
        self.metric_labels: list[tk.Label] = []
        for index, caption in enumerate(("Balance acumulado", "Efectivo acumulado", "Días cuadrados")):
            card = tk.Frame(metrics, bg=self.parent.SURFACE, highlightbackground=self.parent.BORDER, highlightthickness=1, padx=15, pady=12)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            metrics.columnconfigure(index, weight=1)
            tk.Label(card, text=caption, bg=self.parent.SURFACE, fg=self.parent.MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            value = tk.Label(card, text="$ —", bg=self.parent.SURFACE, fg=self.parent.TEXT, font=("Segoe UI", 16, "bold"))
            value.pack(anchor="w", pady=(5, 0))
            self.metric_labels.append(value)
        chart_frame = tk.Frame(self, bg=self.parent.SURFACE, highlightbackground=self.parent.BORDER, highlightthickness=1, padx=12, pady=12)
        chart_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        tk.Label(chart_frame, text="Balance y efectivo por día", bg=self.parent.SURFACE, fg=self.parent.TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        legend = tk.Frame(chart_frame, bg=self.parent.SURFACE)
        legend.pack(anchor="w", pady=(3, 8))
        tk.Label(legend, text="● Balance", bg=self.parent.SURFACE, fg=self.parent.PURPLE, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(legend, text="● Efectivo", bg=self.parent.SURFACE, fg=self.parent.CYAN, font=("Segoe UI", 9)).pack(side="left", padx=13)
        self.canvas = tk.Canvas(chart_frame, bg=self.parent.SURFACE_ALT, highlightthickness=0, height=315)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw_chart())

    def load_period(self, period: str) -> None:
        self.period = period
        for key, button in self.period_buttons.items():
            selected = key == period
            button.configure(bg=self.parent.PURPLE if selected else "#211C37", fg=self.parent.BG if selected else self.parent.TEXT,
                             activebackground=self.parent.PURPLE if selected else "#312852", activeforeground=self.parent.TEXT)
        self.summary_var.set("Cargando datos de Excel...")
        self.canvas.delete("all")
        self.canvas.create_text(30, 30, text="Cargando comparación...", fill=self.parent.MUTED, anchor="w", font=("Segoe UI", 10))
        Thread(target=self._load_worker, args=(period,), daemon=True).start()

    def _load_worker(self, period: str) -> None:
        try:
            records = get_statistics(load_config(), period)
            self.after(0, lambda: self._apply_records(period, records))
        except Exception as error:
            self.after(0, lambda: self._apply_error(error))

    def _apply_records(self, period: str, records: list[dict]) -> None:
        if period != self.period:
            return
        self.records = records
        if not records:
            self.summary_var.set("No hay cuadres registrados en este período.")
        else:
            self.summary_var.set(f"{len(records)} cuadre(s) analizado(s)")
        self.draw_chart()

    def _apply_error(self, error: Exception) -> None:
        self.records = []
        self.summary_var.set(f"No se pudieron obtener estadísticas: {error}")
        self.draw_chart()

    def draw_chart(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 780)
        height = max(canvas.winfo_height(), 300)
        left, right, top, bottom = 64, 24, 25, 44
        chart_w, chart_h = width - left - right, height - top - bottom
        valid = [record for record in self.records if self.parent._number(record.get("balance")) is not None and self.parent._number(record.get("cash")) is not None]
        if not valid:
            canvas.create_text(width / 2, height / 2, text="No hay datos suficientes para graficar este período.", fill=self.parent.MUTED, font=("Segoe UI", 10))
            for label in self.metric_labels:
                label.configure(text="$ —")
            return
        balances = [self.parent._number(record["balance"]) or 0 for record in valid]
        cashes = [self.parent._number(record["cash"]) or 0 for record in valid]
        maximum = max(max(balances), max(cashes), 1)
        minimum = min(min(balances), min(cashes), 0)
        spread = max(maximum - minimum, 1)
        maximum += spread * 0.12
        minimum -= spread * 0.12
        for index in range(5):
            y = top + chart_h * index / 4
            value = maximum - (maximum - minimum) * index / 4
            canvas.create_line(left, y, width - right, y, fill="#302A49")
            canvas.create_text(left - 8, y, text=f"${value:,.0f}", fill=self.parent.MUTED, anchor="e", font=("Segoe UI", 8))
        def point(index: int, value: float) -> tuple[float, float]:
            x = left + (chart_w * index / max(len(valid) - 1, 1))
            y = top + (maximum - value) * chart_h / (maximum - minimum)
            return x, y
        balance_points = [point(index, value) for index, value in enumerate(balances)]
        cash_points = [point(index, value) for index, value in enumerate(cashes)]
        if len(balance_points) > 1:
            canvas.create_line(*[coordinate for item in balance_points for coordinate in item], fill=self.parent.PURPLE, width=3, smooth=True)
            canvas.create_line(*[coordinate for item in cash_points for coordinate in item], fill=self.parent.CYAN, width=3, smooth=True)
        for x, y in balance_points:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=self.parent.PURPLE, outline="")
        for x, y in cash_points:
            canvas.create_rectangle(x - 3, y - 3, x + 3, y + 3, fill=self.parent.CYAN, outline="")
        label_indexes = sorted({0, len(valid) // 2, len(valid) - 1})
        for index in label_indexes:
            x, _ = point(index, balances[index])
            date_label = str(valid[index].get("date", ""))[5:]
            canvas.create_text(x, height - 20, text=date_label, fill=self.parent.MUTED, font=("Segoe UI", 8))
        total_balance, total_cash = sum(balances), sum(cashes)
        squared = sum(1 for balance, cash in zip(balances, cashes) if abs(balance - cash) < 0.005)
        self.metric_labels[0].configure(text=f"$ {total_balance:,.2f}")
        self.metric_labels[1].configure(text=f"$ {total_cash:,.2f}")
        self.metric_labels[2].configure(text=f"{squared} / {len(valid)}")


def main() -> None:
    app = AutoCuadreDashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
