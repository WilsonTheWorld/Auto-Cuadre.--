"""Utilidades de interfaz compartidas: colores, tema, ventana adaptable y zona con scroll."""

from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk

from utils import MONTHS, WEEKDAYS

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
BTN = "#211C37"
BTN_ACTIVE = "#312852"


def to_number(value) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def money(value, empty: str = "$ —") -> str:
    number = to_number(value)
    return empty if number is None else f"$ {number:,.2f}"


def spanish_date(day: date) -> str:
    """Fecha en español sin depender del idioma de Windows."""
    return f"{WEEKDAYS[day.weekday()].capitalize()}, {day.day} de {MONTHS[day.month - 1].lower()} de {day.year}"


def flat_button(parent, text: str, command, *, accent: str | None = None, secondary: bool = False) -> tk.Button:
    background = BTN if secondary else (accent or PURPLE)
    return tk.Button(parent, text=text, command=command, bg=background, fg=TEXT if secondary else BG,
                     activebackground=BTN_ACTIVE if secondary else (accent or PURPLE), activeforeground=TEXT,
                     relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=13, pady=8, cursor="hand2")


def fit_window(window, width: int, height: int, min_width: int = 820, min_height: int = 520) -> None:
    """Tamaño inicial y mínimo que nunca superan la pantalla (monitores pequeños incluidos)."""
    window.update_idletasks()
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    w = min(width, int(screen_w * 0.96))
    h = min(height, int(screen_h * 0.88))  # deja espacio a la barra de tareas
    window.minsize(min(min_width, w), min(min_height, h))
    window.geometry(f"{w}x{h}+{max((screen_w - w) // 2, 0)}+{max((screen_h - h) // 3, 0)}")


def apply_theme(root) -> None:
    """Estilos ttk oscuros. Es seguro llamarlo varias veces."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Card.TLabelframe", background=SURFACE, bordercolor=BORDER, relief="solid")
    style.configure("Card.TLabelframe.Label", background=SURFACE, foreground=TEXT, font=("Segoe UI", 10, "bold"))
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("Body.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Metric.TLabel", background=SURFACE, foreground=TEXT, font=("Segoe UI", 16, "bold"))
    style.configure("Primary.TButton", background=PURPLE, foreground=BG, font=("Segoe UI", 9, "bold"), padding=(13, 8))
    style.map("Primary.TButton", background=[("active", "#A78BFA")])
    style.configure("Secondary.TButton", background=BTN, foreground=TEXT, font=("Segoe UI", 9, "bold"), padding=(11, 8))
    style.map("Secondary.TButton", background=[("active", BTN_ACTIVE)])
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=27, font=("Segoe UI", 9))
    style.configure("Treeview.Heading", background=BTN, foreground=TEXT, font=("Segoe UI", 9, "bold"))
    style.configure("Auto.Horizontal.TProgressbar", troughcolor=BTN, background=PURPLE,
                    bordercolor=BORDER, lightcolor=PURPLE, darkcolor=PURPLE)
    style.configure("TCombobox", fieldbackground=SURFACE_ALT, background=BTN, foreground=TEXT,
                    arrowcolor=TEXT, bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE_ALT)], foreground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", SURFACE_ALT)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)


class ScrollableFrame(tk.Frame):
    """Contenedor con scroll vertical: si la pantalla es pequeña, el contenido se desplaza en vez de cortarse.

    Los widgets se colocan dentro de `.inner`. El ancho se ajusta solo al de la ventana.
    """

    def __init__(self, master, bg: str = BG) -> None:
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, borderwidth=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    def _fit_inner(self) -> None:
        # el contenido ocupa al menos todo el alto visible para que sus filas puedan expandirse
        self.canvas.itemconfigure(self._window, width=self.canvas.winfo_width(),
                                  height=max(self.canvas.winfo_height(), self.inner.winfo_reqheight()))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_inner_configure(self, _event=None) -> None:
        self._fit_inner()

    def _on_canvas_configure(self, _event=None) -> None:
        self._fit_inner()

    def _bind_wheel(self, _event=None) -> None:
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.bind_all("<Button-4>", self._on_wheel)
        self.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event=None) -> None:
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _on_wheel(self, event) -> None:
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            return  # todo cabe: no hay nada que desplazar
        step = -1 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step * 3, "units")
