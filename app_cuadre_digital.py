"""Interfaz de captura, control y avisos para el cuadre diario.

Adaptable a cualquier tamaño de pantalla: todo el contenido vive dentro de una zona con scroll,
las columnas se reorganizan en pantallas estrechas y Excel se consulta en segundo plano.
"""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from tasks import run_in_background
from ui_helpers import (AMBER, BG, BORDER, BTN, GREEN, MUTED, PURPLE, RED, SURFACE, TEXT,
                        ScrollableFrame, apply_theme, fit_window)
from utils import (ConfigurationError, ValidationError, ensure_daily_workbook,
                   load_config, open_with_system, read_daily_values,
                   save_daily_values, validate_non_negative_number)


class AutoCuadreApp(ttk.Frame):
    NARROW = 900  # por debajo de este ancho el panel de estado pasa debajo del formulario

    def __init__(self, master, embedded: bool = False, on_saved=None) -> None:
        super().__init__(master)
        self.embedded = embedded
        self.on_saved = on_saved
        if not embedded:  # ejecución independiente: esta clase es dueña de la ventana
            master.title("Auto Cuadre | Cuadre Digital")
            master.configure(background=BG)
            apply_theme(master)
            fit_window(master, 1100, 700, 700, 460)
            self.grid(sticky="nsew")
            master.columnconfigure(0, weight=1)
            master.rowconfigure(0, weight=1)

        self.saved_receipts: dict[int, dict[str, object]] = {}
        self.new_receipts: list[dict[str, object]] = []
        self.updated_receipts: dict[int, dict[str, object]] = {}
        self.editing: tuple[str, int] | None = None
        self.next_new_id = 1
        self._busy = False
        self._narrow = False
        self._build()
        self.bind("<Configure>", self._relayout)
        self.add_log("Aplicación iniciada. Listo para registrar el cuadre.")
        self._load_saved_values()

    # ------------------------------------------------------------------ construcción
    def _build(self) -> None:
        self.mensualidades_var = tk.StringVar(value="0")
        self.varios_var = tk.StringVar(value="0")
        self.transferencias_var = tk.StringVar(value="0")
        self.efectivo_var = tk.StringVar(value="0")
        self.beneficiario_var = tk.StringVar()
        self.recibo_var = tk.StringVar()
        self.valor_recibo_var = tk.StringVar()
        self.balance_var = tk.StringVar(value="$ 0.00")
        self.difference_var = tk.StringVar(value="$ 0.00")
        self.status_var = tk.StringVar(value="PENDIENTE")
        self.status_detail_var = tk.StringVar(value="Aún no se ha calculado el cuadre.")

        scroll = ScrollableFrame(self)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        header = tk.Frame(root, bg=SURFACE, padx=22, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        tk.Label(header, text="AUTO", bg=PURPLE, fg=BG, font=("Segoe UI", 10, "bold"), padx=10, pady=5).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        tk.Label(header, text="Cuadre Digital", bg=SURFACE, fg=TEXT, font=("Segoe UI", 16, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(header, text="Registro diario, validación y control de caja", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w")
        tk.Label(header, text=datetime.now().strftime("%d/%m/%Y"), bg=BTN, fg=TEXT, font=("Segoe UI", 10, "bold"), padx=12, pady=6).grid(row=0, column=2, rowspan=2, sticky="e")

        self.body = body = tk.Frame(root, bg=BG, padx=16, pady=12)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1, minsize=240)
        body.rowconfigure(0, weight=1)

        self.left = left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)  # la tarjeta de recibos absorbe el espacio sobrante
        self._build_financial_card(left)
        self._build_receipts_card(left)
        self._build_actions(left)
        self._build_status_panel(body)

    def _build_financial_card(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Registro del día", style="Card.TLabelframe", padding=12)
        card.grid(row=0, column=0, sticky="ew")
        for column in (1, 3):
            card.columnconfigure(column, weight=1)
        fields = (("Mensualidades", self.mensualidades_var, 0, 0), ("Ingresos varios", self.varios_var, 0, 2),
                  ("Transferencias", self.transferencias_var, 1, 0), ("Efectivo en caja", self.efectivo_var, 1, 2))
        for label, variable, row, column in fields:
            ttk.Label(card, text=label, style="Body.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(card, textvariable=variable, width=12, font=("Segoe UI", 10)).grid(row=row, column=column + 1, sticky="ew", padx=(0, 14), pady=4)
        ttk.Separator(card, orient="horizontal").grid(row=2, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Label(card, text="Balance del día · E45", style="Body.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Label(card, textvariable=self.balance_var, style="Metric.TLabel").grid(row=3, column=1, sticky="w")
        ttk.Label(card, text="Diferencia · E49", style="Body.TLabel").grid(row=3, column=2, sticky="w")
        ttk.Label(card, textvariable=self.difference_var, style="Metric.TLabel").grid(row=3, column=3, sticky="w")

    def _build_receipts_card(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Recibos de salida", style="Card.TLabelframe", padding=12)
        card.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        card.rowconfigure(2, weight=1)
        fields = (("Beneficiario", self.beneficiario_var, 0, 0), ("No. de recibo", self.recibo_var, 0, 2), ("Valor", self.valor_recibo_var, 1, 0))
        for label, variable, row, column in fields:
            ttk.Label(card, text=label, style="Body.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(card, textvariable=variable, font=("Segoe UI", 10)).grid(row=row, column=column + 1, sticky="ew", padx=(0, 12), pady=4)
        receipt_actions = ttk.Frame(card, style="Card.TFrame")
        receipt_actions.grid(row=1, column=2, columnspan=2, sticky="e", pady=4)
        ttk.Button(receipt_actions, text="Añadir", style="Secondary.TButton", command=self.add_receipt).pack(side="left")
        ttk.Button(receipt_actions, text="Actualizar selec.", style="Secondary.TButton", command=self.update_selected_receipt).pack(side="left", padx=(6, 0))
        ttk.Button(receipt_actions, text="Limpiar", command=self.clear_receipt_form).pack(side="left", padx=(6, 0))

        columns = ("row", "beneficiary", "receipt", "value", "state")
        table_frame = tk.Frame(card, bg=SURFACE)
        table_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(8, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.receipt_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=5, selectmode="browse")
        specs = (("row", "Fila", 50, "center"), ("beneficiary", "Beneficiario", 160, "w"), ("receipt", "No. recibo", 100, "w"),
                 ("value", "Valor", 95, "e"), ("state", "Estado", 90, "center"))
        for column, heading, width, anchor in specs:
            self.receipt_table.heading(column, text=heading)
            self.receipt_table.column(column, width=width, minwidth=40, anchor=anchor, stretch=column == "beneficiary")
        bar = ttk.Scrollbar(table_frame, orient="vertical", command=self.receipt_table.yview)
        self.receipt_table.configure(yscrollcommand=bar.set)
        self.receipt_table.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        self.receipt_table.bind("<<TreeviewSelect>>", self.select_receipt)
        ttk.Label(card, text="Seleccione un recibo existente para modificarlo. Los cambios se aplican al guardar.",
                  style="Body.TLabel", wraplength=480).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def _build_actions(self, parent: tk.Frame) -> None:
        actions = tk.Frame(parent, bg=BG)
        actions.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Imprimir cuadre actual", style="Secondary.TButton", command=self.show_print_menu).pack(side="left", padx=(0, 8))
        self.save_button = ttk.Button(actions, text="Guardar cuadre del día", style="Primary.TButton", command=self.save_daily_data)
        self.save_button.pack(side="left")

    def _build_status_panel(self, parent: tk.Frame) -> None:
        self.status_panel = panel = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(6, weight=1)
        tk.Label(panel, text="Estado y avisos", bg=SURFACE, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.status_badge = tk.Label(panel, textvariable=self.status_var, bg=BTN, fg=TEXT, font=("Segoe UI", 10, "bold"), padx=10, pady=5)
        self.status_badge.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.status_detail = tk.Label(panel, textvariable=self.status_detail_var, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9),
                                      wraplength=210, justify="left")
        self.status_detail.grid(row=2, column=0, sticky="w", pady=(8, 8))
        ttk.Separator(panel, orient="horizontal").grid(row=3, column=0, sticky="ew", pady=(0, 8))
        tk.Label(panel, text="Actividad reciente", bg=SURFACE, fg=TEXT, font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w")
        log_box = tk.Frame(panel, bg="#0B1020")
        log_box.grid(row=6, column=0, sticky="nsew", pady=(6, 0))
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_box, height=8, width=26, bg="#0B1020", fg="#DDD6FE", insertbackground="#DDD6FE", relief="flat",
                                wrap="word", font=("Consolas", 9), padx=8, pady=8, state="disabled")
        scrollbar = ttk.Scrollbar(log_box, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.refresh_button = ttk.Button(panel, text="Actualizar valores", command=self._load_saved_values)
        self.refresh_button.grid(row=7, column=0, sticky="w", pady=(10, 0))

    def _relayout(self, _event=None) -> None:
        """Pantalla estrecha: el panel de estado pasa debajo del formulario en vez de quitarle ancho."""
        narrow = self.winfo_width() < self.NARROW
        if narrow == self._narrow:
            return
        self._narrow = narrow
        if narrow:
            self.body.columnconfigure(1, weight=0, minsize=0)
            self.left.grid_configure(padx=0)
            self.status_panel.grid_configure(row=1, column=0, pady=(12, 0))
            self.status_detail.configure(wraplength=420)
        else:
            self.body.columnconfigure(1, weight=1, minsize=240)
            self.left.grid_configure(padx=(0, 14))
            self.status_panel.grid_configure(row=0, column=1, pady=0)
            self.status_detail.configure(wraplength=210)

    # ------------------------------------------------------------------ utilidades
    @staticmethod
    def _as_number(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _money(cls, value: object) -> str:
        number = cls._as_number(value)
        return "$ 0.00" if number is None else f"$ {number:,.2f}"

    def add_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"[{stamp}] {message}\n\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.save_button, self.refresh_button):
            button.configure(state=state)

    def _parent(self):
        return self.winfo_toplevel()

    # ------------------------------------------------------------------ lectura (en segundo plano)
    def _load_saved_values(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        run_in_background(self, lambda report, cancel: read_daily_values(load_config()),
                          on_done=self._apply_loaded, on_error=self._load_failed)

    def _load_failed(self, error: BaseException) -> None:
        self._set_busy(False)
        self.add_log(f"No se pudieron cargar los valores: {error}")

    def _apply_loaded(self, values) -> None:
        self._set_busy(False)
        if not values:
            self.add_log("No existe un archivo para hoy. Se preparará al guardar el primer registro.")
            return
        for field, variable in (("monthly", self.mensualidades_var), ("other", self.varios_var),
                                ("transfers", self.transferencias_var), ("cash", self.efectivo_var)):
            if values.get(field) is not None:
                variable.set(str(values[field]))
        self.balance_var.set(self._money(values.get("balance")))
        self.difference_var.set(self._money(values.get("difference")))
        self.saved_receipts = {
            int(item["row"]): {"beneficiary": str(item.get("beneficiary", "")), "receipt": str(item.get("receipt", "")),
                               "value": item.get("value", 0)}
            for item in values.get("receipts", [])
        }
        self.updated_receipts.clear()
        self.new_receipts.clear()
        self.refresh_receipts()
        self._report_balance_state(values)
        self.add_log("Datos del cuadre actual cargados desde Excel.")

    def _report_balance_state(self, values: dict[str, object]) -> None:
        balance = self._as_number(values.get("balance"))
        cash = self._as_number(values.get("cash"))
        if balance is None or cash is None:
            self.status_var.set("PENDIENTE")
            self.status_detail_var.set("Faltan valores para evaluar el cuadre.")
            self.status_badge.configure(bg=BTN, fg=TEXT)
            return
        delta = cash - balance
        if abs(delta) < 0.005:
            self.status_var.set("CUADRADO")
            self.status_detail_var.set("El efectivo en caja coincide con el balance del día.")
            self.status_badge.configure(bg="#123F3B", fg=GREEN)
            self.add_log("Cuadre cuadrado: efectivo y balance coinciden.")
        elif delta > 0:
            self.status_var.set("SOBRANTE")
            self.status_detail_var.set(f"Hay un sobrante de {self._money(delta)} frente al balance.")
            self.status_badge.configure(bg="#44350F", fg=AMBER)
            self.add_log(f"Aviso: sobrante detectado de {self._money(delta)}.")
        else:
            self.status_var.set("FALTANTE")
            self.status_detail_var.set(f"Hay un faltante de {self._money(abs(delta))} frente al balance.")
            self.status_badge.configure(bg="#481C31", fg=RED)
            self.add_log(f"Aviso: faltante detectado de {self._money(abs(delta))}.")

    # ------------------------------------------------------------------ recibos
    def refresh_receipts(self) -> None:
        for item in self.receipt_table.get_children():
            self.receipt_table.delete(item)
        for row, receipt in sorted(self.saved_receipts.items()):
            state = "Modificado" if row in self.updated_receipts else "Registrado"
            self.receipt_table.insert("", tk.END, iid=f"saved-{row}", values=(row, receipt["beneficiary"], receipt["receipt"], self._money(receipt["value"]), state))
        for receipt in self.new_receipts:
            self.receipt_table.insert("", tk.END, iid=f"new-{receipt['id']}", values=("Nueva", receipt["beneficiary"], receipt["receipt"], self._money(receipt["value"]), "Pendiente"))

    def _receipt_form_data(self) -> dict[str, object]:
        beneficiary = self.beneficiario_var.get().strip()
        receipt = self.recibo_var.get().strip()
        if not beneficiary or not receipt:
            raise ValidationError("Indique beneficiario y No. de recibo.")
        return {"beneficiary": beneficiary, "receipt": receipt,
                "value": validate_non_negative_number(self.valor_recibo_var.get(), "Valor del recibo", positive=True)}

    def add_receipt(self) -> None:
        try:
            data = self._receipt_form_data()
            data["id"] = self.next_new_id
            self.next_new_id += 1
            self.new_receipts.append(data)
            self.refresh_receipts()
            self.add_log(f"Recibo «{data['receipt']}» preparado para registrar a {data['beneficiary']}.")
            self.clear_receipt_form()
        except ValidationError as error:
            messagebox.showerror("Recibos", str(error), parent=self._parent())

    def select_receipt(self, _event=None) -> None:
        selected = self.receipt_table.selection()
        if not selected:
            return
        kind, raw_id = selected[0].split("-", 1)
        identifier = int(raw_id)
        data = self.saved_receipts[identifier] if kind == "saved" else next(item for item in self.new_receipts if item["id"] == identifier)
        self.editing = (kind, identifier)
        self.beneficiario_var.set(str(data["beneficiary"]))
        self.recibo_var.set(str(data["receipt"]))
        self.valor_recibo_var.set(str(data["value"]))
        description = f"fila {identifier}" if kind == "saved" else "recibo pendiente"
        self.add_log(f"Edición preparada para {description}. Actualice los campos y pulse «Actualizar selec.».")

    def update_selected_receipt(self) -> None:
        if not self.editing:
            messagebox.showinfo("Recibos", "Seleccione un recibo de la tabla para modificarlo.", parent=self._parent())
            return
        try:
            data = self._receipt_form_data()
            kind, identifier = self.editing
            if kind == "saved":
                self.saved_receipts[identifier] = data
                self.updated_receipts[identifier] = data
                self.add_log(f"Modificación preparada para el recibo de la fila {identifier}.")
            else:
                for item in self.new_receipts:
                    if item["id"] == identifier:
                        item.update(data)
                        break
                self.add_log("Recibo pendiente actualizado.")
            self.refresh_receipts()
            self.clear_receipt_form()
        except ValidationError as error:
            messagebox.showerror("Recibos", str(error), parent=self._parent())

    def clear_receipt_form(self) -> None:
        self.editing = None
        self.beneficiario_var.set("")
        self.recibo_var.set("")
        self.valor_recibo_var.set("")
        for item in self.receipt_table.selection():
            self.receipt_table.selection_remove(item)

    # ------------------------------------------------------------------ guardado (en segundo plano)
    def save_daily_data(self, *, show_success: bool = True, then=None) -> None:
        """Valida en pantalla y guarda en Excel sin congelar la ventana. then(path) se llama si todo salió bien."""
        if self._busy:
            return
        parent = self._parent()
        try:
            monthly = validate_non_negative_number(self.mensualidades_var.get(), "Mensualidades")
            other = validate_non_negative_number(self.varios_var.get(), "Ingresos varios")
            transfers = validate_non_negative_number(self.transferencias_var.get(), "Transferencias")
            cash = validate_non_negative_number(self.efectivo_var.get(), "Efectivo en caja")
            if any((self.beneficiario_var.get().strip(), self.recibo_var.get().strip(), self.valor_recibo_var.get().strip())):
                raise ValidationError("Añada o actualice el recibo que está en pantalla, o borre sus campos antes de guardar.")
        except ValidationError as error:
            messagebox.showerror("Auto Cuadre", str(error), parent=parent)
            self.add_log(f"No se guardó el cuadre: {error}")
            return
        new_items = [(str(item["beneficiary"]), str(item["receipt"]), float(item["value"])) for item in self.new_receipts]
        changed_items = [(row, str(item["beneficiary"]), str(item["receipt"]), float(item["value"])) for row, item in self.updated_receipts.items()]
        self._set_busy(True)
        self.add_log("Guardando el cuadre en Excel…")

        def work(report, cancel):
            return save_daily_values(load_config(), monthly=monthly, other=other, transfers=transfers, cash=cash,
                                     new_receipts=new_items, updated_receipts=changed_items)

        def done(result):
            path, values = result
            for item in new_items:
                self.add_log(f"Recibo «{item[1]}» registrado correctamente.")
            for row, *_ in changed_items:
                self.add_log(f"Recibo de la fila {row} modificado correctamente.")
            self._apply_loaded(values)  # el propio guardado devuelve los valores actualizados
            if self.on_saved:
                self.on_saved()
            if show_success:
                messagebox.showinfo("Auto Cuadre", f"Cuadre guardado en:\n{path}", parent=parent)
            if then:
                then(path)

        def failed(error):
            self._set_busy(False)
            if isinstance(error, (ConfigurationError, ValidationError)):
                messagebox.showerror("Auto Cuadre", str(error), parent=parent)
                self.add_log(f"No se guardó el cuadre: {error}")
            else:
                messagebox.showerror("Auto Cuadre - Error", f"No se pudo guardar el cuadre:\n{error}", parent=parent)
                self.add_log(f"Error no esperado al guardar: {error}")

        run_in_background(self, work, on_done=done, on_error=failed)

    # ------------------------------------------------------------------ impresión
    def show_print_menu(self) -> None:
        parent = self._parent()
        dialog = tk.Toplevel(parent)
        dialog.title("Imprimir cuadre actual")
        dialog.resizable(False, False)
        dialog.transient(parent)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.grid(sticky="nsew")
        ttk.Label(frame, text="Imprimir cuadre actual", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Puede guardar los datos en pantalla y abrir Excel para escoger impresora y ajustes.", wraplength=430).grid(row=1, column=0, sticky="w", pady=(8, 14))
        ttk.Button(frame, text="Guardar y abrir en Excel", style="Primary.TButton", command=lambda: self._save_and_open_for_print(dialog)).grid(row=2, column=0, sticky="ew", pady=3)
        ttk.Button(frame, text="Abrir último cuadre guardado", style="Secondary.TButton", command=lambda: self._open_saved_for_print(dialog)).grid(row=3, column=0, sticky="ew", pady=3)
        ttk.Button(frame, text="Imprimir en impresora predeterminada", command=lambda: self._print_default(dialog)).grid(row=4, column=0, sticky="ew", pady=3)
        ttk.Button(frame, text="Cancelar", command=dialog.destroy).grid(row=5, column=0, sticky="e", pady=(12, 0))

    def _save_and_open_for_print(self, dialog: tk.Toplevel) -> None:
        dialog.destroy()

        def opened(path) -> None:
            open_with_system(path)
            self.add_log("Cuadre abierto en Excel para impresión manual.")

        self.save_daily_data(show_success=False, then=opened)

    def _open_saved_for_print(self, dialog: tk.Toplevel) -> None:
        try:
            path = ensure_daily_workbook(load_config())
            dialog.destroy()
            open_with_system(path)
            self.add_log("Último cuadre guardado abierto en Excel.")
        except Exception as error:
            messagebox.showerror("Imprimir cuadre", f"No se pudo abrir el cuadre:\n{error}", parent=dialog)

    def _print_default(self, dialog: tk.Toplevel) -> None:
        if not messagebox.askyesno("Imprimir cuadre", "Se enviará el último cuadre guardado a la impresora predeterminada. ¿Desea continuar?", parent=dialog):
            return
        try:
            path = ensure_daily_workbook(load_config())
            open_with_system(path, "print")
            dialog.destroy()
            self.add_log("Cuadre enviado a la impresora predeterminada.")
        except Exception as error:
            messagebox.showerror("Imprimir cuadre", f"No se pudo enviar a imprimir:\n{error}", parent=dialog)


def main() -> None:
    root = tk.Tk()
    AutoCuadreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
