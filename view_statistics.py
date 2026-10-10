"""Vista de estadísticas (dentro de la ventana principal): período personalizado de hasta 12 meses."""

from __future__ import annotations

from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk

from stats_service import (MAX_MONTHS, compute_statistics, month_bounds, month_label,
                           months_between)
from tasks import run_in_background
from ui_helpers import (AMBER, BG, BORDER, BTN, BTN_ACTIVE, CYAN, MUTED, PURPLE, RED,
                        SURFACE, SURFACE_ALT, TEXT, flat_button, money, to_number)
from utils import MONTHS, ValidationError, load_config

PRESETS = (("week", "Semanal"), ("month", "Mensual"), ("year", "Anual"))
MONTH_NAMES = [name.capitalize() for name in MONTHS]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


class StatisticsView(tk.Frame):
    def __init__(self, master, shell) -> None:
        super().__init__(master, bg=BG)
        self.shell = shell
        self.records: list[dict] = []
        self.task = None
        self._loaded_once = False
        self.summary_var = tk.StringVar(value="Elija un período y pulse Calcular.")
        self.progress_text = tk.StringVar(value="")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.preset_buttons: dict[str, tk.Button] = {}
        self._build()

    # ------------------------------------------------------------------ interfaz
    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)

        header = tk.Frame(self, bg=BG, padx=24, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="Estadísticas", bg=BG, fg=TEXT, font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(header, text="Comparación de balance y efectivo", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=12, pady=(5, 0))

        presets = tk.Frame(self, bg=BG, padx=24)
        presets.grid(row=1, column=0, sticky="ew")
        for key, label in PRESETS:
            button = tk.Button(presets, text=label, command=lambda value=key: self.load_preset(value),
                               relief="flat", bd=0, padx=15, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2")
            button.pack(side="left", padx=(0, 8))
            self.preset_buttons[key] = button
        self.summary_label = tk.Label(presets, textvariable=self.summary_var, bg=BG, fg=MUTED,
                                      font=("Segoe UI", 9), wraplength=520, justify="right")
        self.summary_label.pack(side="right")

        # Selector de rango superior: de mes X a mes Y (máximo 12 meses)
        today = date.today()
        start_year, start_month = _shift_month(today.year, today.month, -2)
        years = [str(y) for y in range(today.year, today.year - 8, -1)]
        range_bar = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=9)
        range_bar.grid(row=2, column=0, sticky="ew", padx=24, pady=(10, 0))
        tk.Label(range_bar, text="Período personalizado", bg=SURFACE, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.from_month = ttk.Combobox(range_bar, values=MONTH_NAMES, state="readonly", width=11)
        self.from_year = ttk.Combobox(range_bar, values=years, state="readonly", width=6)
        self.to_month = ttk.Combobox(range_bar, values=MONTH_NAMES, state="readonly", width=11)
        self.to_year = ttk.Combobox(range_bar, values=years, state="readonly", width=6)
        self.from_month.current(start_month - 1)
        self.from_year.set(str(start_year))
        self.to_month.current(today.month - 1)
        self.to_year.set(str(today.year))
        tk.Label(range_bar, text="De", bg=SURFACE, fg=MUTED).pack(side="left", padx=(14, 4))
        self.from_month.pack(side="left")
        self.from_year.pack(side="left", padx=(4, 0))
        tk.Label(range_bar, text="a", bg=SURFACE, fg=MUTED).pack(side="left", padx=8)
        self.to_month.pack(side="left")
        self.to_year.pack(side="left", padx=(4, 0))
        flat_button(range_bar, "Calcular", self.calculate_range).pack(side="left", padx=(14, 6))
        flat_button(range_bar, "Cancelar", self.cancel, secondary=True).pack(side="left")
        tk.Label(range_bar, text=f"Máx. {MAX_MONTHS} meses", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="right")

        # Barra de progreso global
        progress = tk.Frame(self, bg=BG, padx=24)
        progress.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        progress.columnconfigure(0, weight=1)
        ttk.Progressbar(progress, style="Auto.Horizontal.TProgressbar", variable=self.progress_value,
                        maximum=100, mode="determinate").grid(row=0, column=0, sticky="ew")
        tk.Label(progress, textvariable=self.progress_text, bg=BG, fg=MUTED, font=("Segoe UI", 8),
                 anchor="w").grid(row=1, column=0, sticky="w", pady=(3, 0))

        metrics = tk.Frame(self, bg=BG, padx=24, pady=8)
        metrics.grid(row=4, column=0, sticky="ew")
        self.metric_labels: list[tk.Label] = []
        for index, caption in enumerate(("Balance acumulado", "Efectivo acumulado", "Días cuadrados")):
            card = tk.Frame(metrics, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=9)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 8, 0))
            metrics.columnconfigure(index, weight=1)
            tk.Label(card, text=caption, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            value = tk.Label(card, text="$ —", bg=SURFACE, fg=TEXT, font=("Segoe UI", 15, "bold"))
            value.pack(anchor="w", pady=(3, 0))
            self.metric_labels.append(value)

        # Tabla por mes (se llena a medida que cada mes termina) + gráfico
        body = tk.Frame(self, bg=BG, padx=24)
        body.grid(row=5, column=0, sticky="nsew", pady=(0, 14))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        columns = ("month", "days", "balance", "cash", "difference", "squared", "state")
        specs = (("month", "Mes", 120, "w"), ("days", "Cuadres", 70, "center"), ("balance", "Balance", 110, "e"),
                 ("cash", "Efectivo", 110, "e"), ("difference", "Diferencia", 100, "e"),
                 ("squared", "Cuadrados", 80, "center"), ("state", "Estado", 100, "center"))
        table_frame = tk.Frame(body, bg=BG)
        table_frame.grid(row=0, column=0, sticky="ew")
        table_frame.columnconfigure(0, weight=1)
        self.month_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=4, selectmode="none")
        for column, heading, width, anchor in specs:
            self.month_table.heading(column, text=heading)
            self.month_table.column(column, width=width, minwidth=60, anchor=anchor, stretch=column == "month")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.month_table.yview)
        self.month_table.configure(yscrollcommand=scrollbar.set)
        self.month_table.grid(row=0, column=0, sticky="ew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        chart_frame = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=10)
        chart_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        top = tk.Frame(chart_frame, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text="Balance y efectivo por día", bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(top, text="● Balance", bg=SURFACE, fg=PURPLE, font=("Segoe UI", 9)).pack(side="left", padx=(14, 0))
        tk.Label(top, text="● Efectivo", bg=SURFACE, fg=CYAN, font=("Segoe UI", 9)).pack(side="left", padx=10)
        self.canvas = tk.Canvas(chart_frame, bg=SURFACE_ALT, highlightthickness=0, height=150)
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas.bind("<Configure>", lambda _event: self.draw_chart())
        self._highlight_preset(None)

    def _highlight_preset(self, active: str | None) -> None:
        for key, button in self.preset_buttons.items():
            selected = key == active
            button.configure(bg=PURPLE if selected else BTN, fg=BG if selected else TEXT,
                             activebackground=PURPLE if selected else BTN_ACTIVE, activeforeground=TEXT)

    # ------------------------------------------------------------------ ciclo de vida
    def on_show(self) -> None:
        if not self._loaded_once:
            self._loaded_once = True
            self.load_preset("week")

    def invalidate(self) -> None:
        """La configuración cambió (rutas): recalcular la próxima vez que se muestre."""
        self._loaded_once = False

    # ------------------------------------------------------------------ acciones
    def load_preset(self, key: str) -> None:
        today = date.today()
        if key == "week":
            first = today - timedelta(days=today.weekday())
        elif key == "month":
            first = today.replace(day=1)
        else:
            first = today.replace(month=1, day=1)
        self._highlight_preset(key)
        self.start(first, today)

    def calculate_range(self) -> None:
        try:
            first = month_bounds(int(self.from_year.get()), self.from_month.current() + 1)[0]
            last = month_bounds(int(self.to_year.get()), self.to_month.current() + 1)[1]
        except (ValueError, tk.TclError):
            return self._show_message("Elija el mes y el año del período.", error=True)
        self._highlight_preset(None)
        self.start(first, last)

    def cancel(self) -> None:
        if self.task and self.task.active:
            self.task.cancel()
            self.progress_text.set("Cancelado")
            self._show_message("Cálculo cancelado. Se muestran los meses ya calculados.")

    def start(self, first: date, last: date) -> None:
        try:
            months = months_between(first, last)
        except ValidationError as error:
            return self._show_message(str(error), error=True)
        if self.task and self.task.active:
            self.task.cancel(silent=True)
        self.records = []
        self.month_table.delete(*self.month_table.get_children())
        for year, month in months:
            self.month_table.insert("", "end", iid=f"{year}-{month}",
                                    values=(month_label(year, month), "—", "—", "—", "—", "—", "Pendiente"))
        for label in self.metric_labels:
            label.configure(text="$ —")
        self.progress_value.set(0)
        self.progress_text.set("Preparando…")
        self._show_message(f"Calculando {len(months)} mes(es)…")
        self.draw_chart()
        self.task = run_in_background(
            self,
            lambda report, cancel: compute_statistics(load_config(), first, last, report, cancel),
            on_progress=self._on_progress, on_done=self._on_done, on_error=self._on_error)

    # ------------------------------------------------------------------ resultados parciales y finales
    def _on_progress(self, fraction: float, text: str, data) -> None:
        self.progress_value.set(fraction * 100)
        self.progress_text.set(text)
        if not data:
            return
        if data["event"] == "month_start":
            key = f"{data['key'][0]}-{data['key'][1]}"
            if self.month_table.exists(key):
                self.month_table.set(key, "state", "Calculando…")
        elif data["event"] == "month_done":
            summary = data["summary"]
            key = f"{summary['key'][0]}-{summary['key'][1]}"
            if self.month_table.exists(key):
                self.month_table.item(key, values=(
                    summary["label"], summary["days"], money(summary["balance"]), money(summary["cash"]),
                    money(summary["difference"]), f"{summary['squared']} / {summary['days']}", "Listo"))
            self.records.extend(summary["records"])
            self.draw_chart()

    def _on_done(self, result: dict) -> None:
        self.records = result["records"]
        self.progress_value.set(100)
        self.progress_text.set("Cancelado" if result["cancelled"] else "Completado")
        notes = []
        if result["unreadable"]:
            notes.append(f"{result['unreadable']} archivo(s) no se pudieron leer")
        if result["engine"] == "excel":
            notes.append("lectura con Excel; instale xlrd para acelerar")
        extra = f" · {'; '.join(notes)}" if notes else ""
        if not result["records"]:
            self._show_message("No hay cuadres registrados en este período." + extra)
        else:
            self._show_message(f"{len(result['records'])} cuadre(s) analizado(s){extra}",
                               warn=bool(result["unreadable"]))
        self.draw_chart()

    def _on_error(self, error: BaseException) -> None:
        self.progress_text.set("Error")
        self._show_message(f"No se pudieron obtener estadísticas: {error}", error=True)

    def _show_message(self, text: str, *, error: bool = False, warn: bool = False) -> None:
        self.summary_var.set(text)
        self.summary_label.configure(fg=RED if error else (AMBER if warn else MUTED))

    # ------------------------------------------------------------------ gráfico
    def draw_chart(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 140)
        left, right, top, bottom = 64, 24, 20, 34
        chart_w, chart_h = width - left - right, height - top - bottom
        valid = [r for r in self.records if to_number(r.get("balance")) is not None and to_number(r.get("cash")) is not None]
        if not valid:
            canvas.create_text(width / 2, height / 2, text="No hay datos suficientes para graficar este período.",
                               fill=MUTED, font=("Segoe UI", 10))
            if not self.records:
                for label in self.metric_labels:
                    label.configure(text="$ —")
            return
        balances = [to_number(r["balance"]) or 0 for r in valid]
        cashes = [to_number(r["cash"]) or 0 for r in valid]
        maximum = max(max(balances), max(cashes), 1)
        minimum = min(min(balances), min(cashes), 0)
        spread = max(maximum - minimum, 1)
        maximum += spread * 0.12
        minimum -= spread * 0.12
        for index in range(5):
            y = top + chart_h * index / 4
            value = maximum - (maximum - minimum) * index / 4
            canvas.create_line(left, y, width - right, y, fill="#302A49")
            canvas.create_text(left - 8, y, text=f"${value:,.0f}", fill=MUTED, anchor="e", font=("Segoe UI", 8))

        def point(index: int, value: float) -> tuple[float, float]:
            return (left + chart_w * index / max(len(valid) - 1, 1),
                    top + (maximum - value) * chart_h / (maximum - minimum))

        balance_points = [point(i, v) for i, v in enumerate(balances)]
        cash_points = [point(i, v) for i, v in enumerate(cashes)]
        if len(balance_points) > 1:
            canvas.create_line(*[c for p in balance_points for c in p], fill=PURPLE, width=3, smooth=True)
            canvas.create_line(*[c for p in cash_points for c in p], fill=CYAN, width=3, smooth=True)
        for x, y in balance_points:
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=PURPLE, outline="")
        for x, y in cash_points:
            canvas.create_rectangle(x - 3, y - 3, x + 3, y + 3, fill=CYAN, outline="")
        for index in sorted({0, len(valid) // 2, len(valid) - 1}):
            x, _ = point(index, balances[index])
            canvas.create_text(x, height - 14, text=str(valid[index].get("date", ""))[5:], fill=MUTED, font=("Segoe UI", 8))
        squared = sum(1 for b, c in zip(balances, cashes) if abs(b - c) < 0.005)
        self.metric_labels[0].configure(text=f"$ {sum(balances):,.2f}")
        self.metric_labels[1].configure(text=f"$ {sum(cashes):,.2f}")
        self.metric_labels[2].configure(text=f"{squared} / {len(valid)}")
