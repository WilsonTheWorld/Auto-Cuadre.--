"""Vista de configuración: rutas de trabajo, días laborables y origen de actualizaciones."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from ui_helpers import (AMBER, BG, BORDER, GREEN, MUTED, RED, SURFACE, SURFACE_ALT, TEXT,
                        ScrollableFrame, flat_button)
from utils import (DATE_FORMATS, DEFAULT_DATE_FORMAT, DEFAULT_WORKING_DAYS, WEEKDAYS,
                   ConfigurationError, load_config, save_config)
from version import __version__


class SettingsView(tk.Frame):
    def __init__(self, master, shell) -> None:
        super().__init__(master, bg=BG)
        self.shell = shell
        self.holidays: list[str] = []
        self.template_var = tk.StringVar()
        self.base_var = tk.StringVar()
        self.update_var = tk.StringVar()
        self.today_var = tk.BooleanVar(value=True)
        self.day_vars = [tk.BooleanVar(value=i in DEFAULT_WORKING_DAYS) for i in range(7)]
        self.holiday_entry = tk.StringVar()
        self.message_var = tk.StringVar()
        self._build()

    # ------------------------------------------------------------------ interfaz
    def _section(self, parent, title: str, hint: str) -> tk.Frame:
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=18, pady=14)
        card.pack(fill="x", pady=(0, 12))
        tk.Label(card, text=title, bg=SURFACE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(card, text=hint, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9), wraplength=700,
                 justify="left").pack(anchor="w", pady=(2, 10))
        return card

    def _path_row(self, parent, label: str, variable: tk.StringVar, browse) -> None:
        tk.Label(parent, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", pady=(2, 8))
        row.columnconfigure(0, weight=1)
        tk.Entry(row, textvariable=variable, bg=SURFACE_ALT, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="ew", ipady=5)
        flat_button(row, "Examinar…", browse, secondary=True).grid(row=0, column=1, padx=(8, 0))

    def _build(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        scroll = ScrollableFrame(self)
        scroll.grid(row=0, column=0, sticky="nsew")
        body = tk.Frame(scroll.inner, bg=BG, padx=28, pady=14)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Configuración", bg=BG, fg=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(body, text=f"Auto Cuadre {__version__}", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12))

        paths = self._section(body, "Rutas de trabajo", "Modelo de Excel y carpeta que contiene «CUADRE [año] / [MES]». "
                              "Los cambios se aplican al guardar, sin reiniciar.")
        self._path_row(paths, "Modelo de Excel (.xls)", self.template_var, self._browse_template)
        self._path_row(paths, "Carpeta de cuadres", self.base_var, self._browse_base)

        rules = self._section(body, "Días laborables", "Los avisos de «cuadre faltante» solo se generan para los días marcados. "
                              "Cada empresa puede ajustarlo según sus días de operación.")
        days = tk.Frame(rules, bg=SURFACE)
        days.pack(anchor="w")
        for index, name in enumerate(WEEKDAYS):
            tk.Checkbutton(days, text=name.capitalize(), variable=self.day_vars[index], bg=SURFACE, fg=TEXT,
                           selectcolor=SURFACE_ALT, activebackground=SURFACE, activeforeground=TEXT,
                           font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))
        tk.Checkbutton(rules, text="Avisar también del día de hoy mientras no tenga cuadre", variable=self.today_var,
                       bg=SURFACE, fg=TEXT, selectcolor=SURFACE_ALT, activebackground=SURFACE,
                       activeforeground=TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))

        tk.Label(rules, text="Fechas no laborables adicionales (feriados, cierres)", bg=SURFACE, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(14, 4))
        holiday_row = tk.Frame(rules, bg=SURFACE)
        holiday_row.pack(anchor="w", fill="x")
        tk.Entry(holiday_row, textvariable=self.holiday_entry, width=14, bg=SURFACE_ALT, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=("Segoe UI", 10)).pack(side="left", ipady=4)
        tk.Label(holiday_row, text="dd/mm/aaaa", bg=SURFACE, fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=6)
        flat_button(holiday_row, "Añadir", self._add_holiday, secondary=True).pack(side="left")
        flat_button(holiday_row, "Quitar seleccionada", self._remove_holiday, secondary=True).pack(side="left", padx=(8, 0))
        self.holiday_list = tk.Listbox(rules, height=4, bg=SURFACE_ALT, fg=TEXT, relief="flat", highlightthickness=0,
                                       selectbackground="#312852", font=("Segoe UI", 9), exportselection=False)
        self.holiday_list.pack(fill="x", pady=(8, 0))

        dates = self._section(body, "Formato de fecha del cuadre", "Cómo se escribe la fecha dentro del archivo de cada cuadre (celda A5). "
                              "Se guarda como fecha real de Excel, así no depende del idioma de Windows. Solo afecta a los cuadres nuevos.")
        self.date_combo = ttk.Combobox(dates, values=list(DATE_FORMATS.values()), state="readonly", width=30)
        self.date_combo.pack(anchor="w")

        updates = self._section(body, "Actualizaciones automáticas", "Dirección del archivo version.json que publica las versiones "
                                "nuevas (https://… o una carpeta compartida). Déjelo vacío para desactivar las actualizaciones.")
        self._path_row(updates, "Origen de actualizaciones", self.update_var, self._browse_manifest)

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(2, 0))
        flat_button(actions, "Guardar configuración", self.save).pack(side="left")
        flat_button(actions, "Descartar cambios", self.load, secondary=True).pack(side="left", padx=(8, 0))
        self.message_label = tk.Label(actions, textvariable=self.message_var, bg=BG, fg=MUTED, font=("Segoe UI", 9),
                                      wraplength=520, justify="left")
        self.message_label.pack(side="left", padx=14)

    # ------------------------------------------------------------------ datos
    def on_show(self) -> None:
        self.load()

    def load(self) -> None:
        try:
            config = load_config()
            self.message("")
        except ConfigurationError as error:
            config = {"template_path": "", "base_dir": "", "working_days": list(DEFAULT_WORKING_DAYS),
                      "holidays": [], "count_today_as_pending": True, "update_manifest_url": "",
                      "date_format": DEFAULT_DATE_FORMAT}
            self.message(f"{error} Complete los datos y guarde.", AMBER)
        self.template_var.set(config["template_path"])
        self.base_var.set(config["base_dir"])
        self.update_var.set(config["update_manifest_url"])
        self.today_var.set(config["count_today_as_pending"])
        self.date_combo.set(DATE_FORMATS[config["date_format"]])
        for index, variable in enumerate(self.day_vars):
            variable.set(index in config["working_days"])
        self.holidays = list(config["holidays"])
        self._refresh_holidays()

    def message(self, text: str, color: str = MUTED) -> None:
        self.message_var.set(text)
        self.message_label.configure(fg=color)

    def _refresh_holidays(self) -> None:
        self.holiday_list.delete(0, "end")
        for iso in self.holidays:
            self.holiday_list.insert("end", date.fromisoformat(iso).strftime("%d/%m/%Y"))

    def _add_holiday(self) -> None:
        try:
            day = datetime.strptime(self.holiday_entry.get().strip(), "%d/%m/%Y").date()
        except ValueError:
            return self.message("Escriba la fecha como dd/mm/aaaa.", RED)
        if day.isoformat() not in self.holidays:
            self.holidays = sorted([*self.holidays, day.isoformat()])
        self.holiday_entry.set("")
        self._refresh_holidays()

    def _remove_holiday(self) -> None:
        selected = self.holiday_list.curselection()
        if selected:
            del self.holidays[selected[0]]
            self._refresh_holidays()

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(), title="Modelo de Excel",
                                          filetypes=[("Excel 97-2003", "*.xls")],
                                          initialdir=str(Path(self.template_var.get()).parent) if self.template_var.get() else None)
        if path:
            self.template_var.set(str(Path(path)))

    def _browse_base(self) -> None:
        path = filedialog.askdirectory(parent=self.winfo_toplevel(), title="Carpeta de cuadres",
                                       initialdir=self.base_var.get() or None)
        if path:
            self.base_var.set(str(Path(path)))

    def _browse_manifest(self) -> None:
        path = filedialog.askopenfilename(parent=self.winfo_toplevel(), title="version.json de actualizaciones",
                                          filetypes=[("Manifiesto", "*.json")])
        if path:
            self.update_var.set(str(Path(path)))

    def save(self) -> None:
        template, base = self.template_var.get().strip(), self.base_var.get().strip()
        manifest = self.update_var.get().strip()
        days = [index for index, variable in enumerate(self.day_vars) if variable.get()]
        date_format = next((code for code, label in DATE_FORMATS.items() if label == self.date_combo.get()),
                           DEFAULT_DATE_FORMAT)
        errors = []
        if not (Path(template).is_file() and template.lower().endswith(".xls")):
            errors.append("El modelo debe ser un archivo .xls existente.")
        if not Path(base).is_dir():
            errors.append("La carpeta de cuadres no existe.")
        if not days:
            errors.append("Marque al menos un día laborable.")
        if manifest.lower().startswith("http://"):
            errors.append("El origen de actualizaciones debe usar HTTPS (o ser una carpeta).")
        if errors:
            return self.message(" ".join(errors), RED)
        try:
            save_config({"template_path": template, "base_dir": base, "working_days": days,
                         "holidays": self.holidays, "count_today_as_pending": self.today_var.get(),
                         "update_manifest_url": manifest, "date_format": date_format})
        except OSError as error:
            return self.message(f"No se pudo guardar config.json: {error}", RED)
        self.message("Configuración guardada.", GREEN)
        self.shell.on_config_changed()
