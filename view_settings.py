"""Vista de configuración: rutas de trabajo, origen de actualizaciones y días laborables."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox

from ui_helpers import BG, BORDER, MUTED, SURFACE, SURFACE_ALT, TEXT, ScrollableFrame, flat_button
from utils import ConfigurationError, ensure_configuration, load_config, save_config

DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


class SettingsView(tk.Frame):
    def __init__(self, master, shell) -> None:
        super().__init__(master, bg=BG)
        self.shell = shell
        self.vars = {key: tk.StringVar() for key in ("template_path", "base_dir", "update_manifest_url", "holidays")}
        self.days = [tk.BooleanVar() for _ in DAYS]
        self.alert_today = tk.BooleanVar(value=True)
        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)
        card = tk.Frame(scroll.inner, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=18)
        card.pack(fill="x", padx=30, pady=20, anchor="n")
        card.columnconfigure(1, weight=1)
        tk.Label(card, text="Configuración", bg=SURFACE, fg=TEXT, font=("Segoe UI", 15, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        rows = (("Modelo .xls", "template_path", "file"),
                ("Carpeta principal de cuadres", "base_dir", "dir"),
                ("Origen de actualizaciones (URL https o ruta de version.json)", "update_manifest_url", "manifest"))
        for index, (label, key, kind) in enumerate(rows, start=1):
            tk.Label(card, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(row=index, column=0, sticky="w", pady=5, padx=(0, 10))
            tk.Entry(card, textvariable=self.vars[key], bg=SURFACE_ALT, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=("Segoe UI", 10)).grid(row=index, column=1, sticky="ew", ipady=5)
            flat_button(card, "Buscar…", lambda k=key, t=kind: self._browse(k, t), secondary=True).grid(row=index, column=2, padx=(8, 0))

        tk.Label(card, text="Días laborables (se avisa si falta el cuadre de estos días)", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).grid(row=5, column=0, columnspan=3, sticky="w", pady=(18, 4))
        days = tk.Frame(card, bg=SURFACE)
        days.grid(row=6, column=0, columnspan=3, sticky="w")
        for index, name in enumerate(DAYS):
            tk.Checkbutton(days, text=name, variable=self.days[index], bg=SURFACE, fg=TEXT, selectcolor=SURFACE_ALT,
                           activebackground=SURFACE, activeforeground=TEXT).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 14))

        tk.Label(card, text="Feriados (AAAA-MM-DD separados por coma)", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=7, column=0, sticky="w", pady=(14, 4))
        tk.Entry(card, textvariable=self.vars["holidays"], bg=SURFACE_ALT, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 10)).grid(row=7, column=1, columnspan=2, sticky="ew", ipady=5, pady=(14, 0))
        tk.Checkbutton(card, text="Avisar también si falta el cuadre de hoy", variable=self.alert_today, bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE_ALT, activebackground=SURFACE, activeforeground=TEXT).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

        buttons = tk.Frame(card, bg=SURFACE)
        buttons.grid(row=9, column=0, columnspan=3, sticky="w", pady=(18, 0))
        flat_button(buttons, "Guardar configuración", self.save).pack(side="left")
        flat_button(buttons, "Descartar cambios", self.load, secondary=True).pack(side="left", padx=(8, 0))
        self.load()

    def load(self) -> None:
        try:
            config = load_config()
        except ConfigurationError as error:
            messagebox.showerror("Configuración", str(error), parent=self.winfo_toplevel())
            return
        for key, variable in self.vars.items():
            value = config.get(key, "")
            variable.set(", ".join(value) if isinstance(value, list) else str(value))
        for index, variable in enumerate(self.days):
            variable.set(index in config["workdays"])
        self.alert_today.set(bool(config.get("alert_today", True)))

    def _browse(self, key: str, kind: str) -> None:
        if kind == "file":
            path = filedialog.askopenfilename(parent=self.winfo_toplevel(), filetypes=[("Excel 97-2003", "*.xls")])
        elif kind == "manifest":
            path = filedialog.askopenfilename(parent=self.winfo_toplevel(), filetypes=[("Manifiesto", "*.json")])
        else:
            path = filedialog.askdirectory(parent=self.winfo_toplevel())
        if path:
            self.vars[key].set(path.replace("/", "\\"))

    def save(self) -> None:
        parent = self.winfo_toplevel()
        try:
            config = load_config()
        except ConfigurationError:
            config = {}
        holidays = []
        for part in self.vars["holidays"].get().replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                holidays.append(date.fromisoformat(part).isoformat())
            except ValueError:
                messagebox.showerror("Configuración", f"Feriado no válido: «{part}». Use el formato AAAA-MM-DD.", parent=parent)
                return
        config.update({key: self.vars[key].get().strip() for key in ("template_path", "base_dir", "update_manifest_url")})
        config["workdays"] = [index for index, variable in enumerate(self.days) if variable.get()]
        config["holidays"] = sorted(set(holidays))
        config["alert_today"] = bool(self.alert_today.get())
        try:
            ensure_configuration(config)
        except ConfigurationError as error:
            messagebox.showerror("Configuración", str(error), parent=parent)
            return
        try:
            save_config(config)
        except OSError as error:
            messagebox.showerror("Configuración", f"No se pudo guardar: {error}", parent=parent)
            return
        self.shell.on_config_changed()
        messagebox.showinfo("Configuración", "Configuración guardada.", parent=parent)
