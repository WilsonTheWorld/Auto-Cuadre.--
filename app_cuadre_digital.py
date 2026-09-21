"""Interfaz de captura, control y avisos para el cuadre diario."""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from utils import (ConfigurationError, ValidationError, ensure_daily_workbook,
                   load_config, open_with_system, read_daily_values,
                   save_daily_values, validate_non_negative_number)


class AutoCuadreApp(ttk.Frame):
    BACKGROUND = "#090814"
    SURFACE = "#121023"
    BORDER = "#2A2445"
    NAVY = "#121023"
    BLUE = "#8B5CF6"
    GREEN = "#2DD4BF"
    AMBER = "#FBBF24"
    RED = "#FB7185"
    SLATE = "#A8A2C7"
    TEXT = "#F4F1FF"

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.master = master
        self.master.title("Auto Cuadre | Cuadre Digital")
        self.master.minsize(1080, 690)
        self.master.configure(background=self.BACKGROUND)
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        self.saved_receipts: dict[int, dict[str, object]] = {}
        self.new_receipts: list[dict[str, object]] = []
        self.updated_receipts: dict[int, dict[str, object]] = {}
        self.editing: tuple[str, int] | None = None
        self.next_new_id = 1
        self._configure_styles()
        self._build()
        self.add_log("Aplicación iniciada. Listo para registrar el cuadre.")
        self._load_saved_values()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.master)
        style.theme_use("clam")
        style.configure("Card.TLabelframe", background=self.SURFACE, bordercolor=self.BORDER, relief="solid")
        style.configure("Card.TLabelframe.Label", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("Card.TFrame", background=self.SURFACE)
        style.configure("Body.TLabel", background=self.SURFACE, foreground=self.SLATE, font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 16, "bold"))
        style.configure("Primary.TButton", background=self.BLUE, foreground=self.BACKGROUND, font=("Segoe UI", 9, "bold"), padding=(13, 8))
        style.map("Primary.TButton", background=[("active", "#A78BFA")])
        style.configure("Secondary.TButton", background="#211C37", foreground=self.TEXT, font=("Segoe UI", 9, "bold"), padding=(11, 8))
        style.map("Secondary.TButton", background=[("active", "#312852")])
        style.configure("Treeview", background=self.SURFACE, fieldbackground=self.SURFACE, foreground=self.TEXT, rowheight=27, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#211C37", foreground=self.TEXT, font=("Segoe UI", 9, "bold"))

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

        header = tk.Frame(self, bg=self.NAVY, padx=28, pady=19)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        tk.Label(header, text="AUTO", bg=self.BLUE, fg=self.BACKGROUND, font=("Segoe UI", 11, "bold"), padx=11, pady=7).grid(row=0, column=0, rowspan=2, padx=(0, 13))
        tk.Label(header, text="Cuadre Digital", bg=self.NAVY, fg=self.TEXT, font=("Segoe UI", 18, "bold")).grid(row=0, column=1, sticky="w")
        tk.Label(header, text="Registro diario, validación y control de caja", bg=self.NAVY, fg=self.SLATE, font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", pady=(2, 0))
        self.date_label = tk.Label(header, text=datetime.now().strftime("%d/%m/%Y"), bg="#211C37", fg=self.TEXT, font=("Segoe UI", 10, "bold"), padx=12, pady=7)
        self.date_label.grid(row=0, column=2, rowspan=2, sticky="e")

        body = tk.Frame(self, bg=self.BACKGROUND, padx=22, pady=20)
        body.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1, minsize=290)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=self.BACKGROUND)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        self._build_financial_card(left)
        self._build_receipts_card(left)
        self._build_actions(left)
        self._build_status_panel(body)

    def _build_financial_card(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Registro del día", style="Card.TLabelframe", padding=15)
        card.grid(row=0, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        fields = (("Mensualidades", self.mensualidades_var, 0, 0), ("Ingresos varios", self.varios_var, 0, 2),
                  ("Transferencias", self.transferencias_var, 1, 0), ("Efectivo en caja", self.efectivo_var, 1, 2))
        for label, variable, row, column in fields:
            ttk.Label(card, text=label, style="Body.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 8), pady=6)
            ttk.Entry(card, textvariable=variable, width=18, font=("Segoe UI", 10)).grid(row=row, column=column + 1, sticky="ew", padx=(0, 18), pady=6)

        separator = ttk.Separator(card, orient="horizontal")
        separator.grid(row=2, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(card, text="Balance del día · E45", style="Body.TLabel").grid(row=3, column=0, sticky="w")
        ttk.Label(card, textvariable=self.balance_var, style="Metric.TLabel").grid(row=3, column=1, sticky="w")
        ttk.Label(card, text="Diferencia · E49", style="Body.TLabel").grid(row=3, column=2, sticky="w")
        ttk.Label(card, textvariable=self.difference_var, style="Metric.TLabel").grid(row=3, column=3, sticky="w")

    def _build_receipts_card(self, parent: tk.Frame) -> None:
        card = ttk.LabelFrame(parent, text="Recibos de salida", style="Card.TLabelframe", padding=15)
        card.grid(row=1, column=0, sticky="nsew", pady=(15, 0))
        card.columnconfigure(1, weight=1)
        card.columnconfigure(3, weight=1)
        fields = (("Beneficiario", self.beneficiario_var, 0, 0), ("No. de recibo", self.recibo_var, 0, 2), ("Valor", self.valor_recibo_var, 1, 0))
        for label, variable, row, column in fields:
            ttk.Label(card, text=label, style="Body.TLabel").grid(row=row, column=column, sticky="w", padx=(0, 8), pady=5)
            ttk.Entry(card, textvariable=variable, font=("Segoe UI", 10)).grid(row=row, column=column + 1, sticky="ew", padx=(0, 14), pady=5)
        receipt_actions = ttk.Frame(card, style="Card.TFrame")
        receipt_actions.grid(row=1, column=2, columnspan=2, sticky="e", pady=5)
        ttk.Button(receipt_actions, text="Añadir recibo", style="Secondary.TButton", command=self.add_receipt).pack(side="left")
        ttk.Button(receipt_actions, text="Actualizar seleccionado", style="Secondary.TButton", command=self.update_selected_receipt).pack(side="left", padx=(8, 0))
        ttk.Button(receipt_actions, text="Limpiar", command=self.clear_receipt_form).pack(side="left", padx=(8, 0))

        columns = ("row", "beneficiary", "receipt", "value", "state")
        self.receipt_table = ttk.Treeview(card, columns=columns, show="headings", height=8, selectmode="browse")
        specs = (("row", "Fila", 55, "center"), ("beneficiary", "Beneficiario", 220, "w"), ("receipt", "No. recibo", 130, "w"), ("value", "Valor", 105, "e"), ("state", "Estado", 120, "center"))
        for column, heading, width, anchor in specs:
            self.receipt_table.heading(column, text=heading)
            self.receipt_table.column(column, width=width, anchor=anchor, stretch=column == "beneficiary")
        self.receipt_table.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        self.receipt_table.bind("<<TreeviewSelect>>", self.select_receipt)
        ttk.Label(card, text="Seleccione un recibo existente para modificarlo. Los cambios se aplican al guardar el cuadre.", style="Body.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", pady=(7, 0))

    def _build_actions(self, parent: tk.Frame) -> None:
        actions = tk.Frame(parent, bg=self.BACKGROUND)
        actions.grid(row=3, column=0, sticky="e", pady=(17, 0))
        ttk.Button(actions, text="Imprimir cuadre actual", style="Secondary.TButton", command=self.show_print_menu).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Guardar cuadre del día", style="Primary.TButton", command=self.save_daily_data).pack(side="left")

    def _build_status_panel(self, parent: tk.Frame) -> None:
        panel = tk.Frame(parent, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1, padx=16, pady=16)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        tk.Label(panel, text="Estado y avisos", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        tk.Label(panel, text="Seguimiento automático del cuadre", bg=self.SURFACE, fg=self.SLATE, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(2, 12))
        self.status_badge = tk.Label(panel, textvariable=self.status_var, bg="#211C37", fg=self.TEXT, font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        self.status_badge.grid(row=2, column=0, sticky="w")
        tk.Label(panel, textvariable=self.status_detail_var, bg=self.SURFACE, fg=self.SLATE, font=("Segoe UI", 9), wraplength=255, justify="left").grid(row=3, column=0, sticky="w", pady=(9, 15))
        ttk.Separator(panel, orient="horizontal").grid(row=4, column=0, sticky="ew", pady=(0, 12))
        tk.Label(panel, text="Actividad reciente", bg=self.SURFACE, fg=self.TEXT, font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w")
        log_box = tk.Frame(panel, bg="#0B1020")
        log_box.grid(row=6, column=0, sticky="nsew", pady=(8, 0))
        panel.rowconfigure(6, weight=1)
        self.log_text = tk.Text(log_box, height=22, bg="#0B1020", fg="#DDD6FE", insertbackground="#DDD6FE", relief="flat", wrap="word", font=("Consolas", 9), padx=10, pady=10, state="disabled")
        scrollbar = ttk.Scrollbar(log_box, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        log_box.rowconfigure(0, weight=1)
        log_box.columnconfigure(0, weight=1)
        ttk.Button(panel, text="Actualizar valores", command=self._load_saved_values).grid(row=7, column=0, sticky="w", pady=(12, 0))

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

    def _load_saved_values(self) -> None:
        try:
            values = read_daily_values(load_config())
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
                int(item["row"]): {"beneficiary": str(item.get("beneficiary", "")), "receipt": str(item.get("receipt", "")), "value": item.get("value", 0)}
                for item in values.get("receipts", [])
            }
            self.updated_receipts.clear()
            self.new_receipts.clear()
            self.refresh_receipts()
            self._report_balance_state(values)
            self.add_log("Datos del cuadre actual cargados desde Excel.")
        except Exception as error:
            self.add_log(f"No se pudieron cargar los valores: {error}")

    def _report_balance_state(self, values: dict[str, object]) -> None:
        balance = self._as_number(values.get("balance"))
        cash = self._as_number(values.get("cash"))
        if balance is None or cash is None:
            self.status_var.set("PENDIENTE")
            self.status_detail_var.set("Faltan valores para evaluar el cuadre.")
            self.status_badge.configure(bg="#211C37", fg=self.TEXT)
            return
        delta = cash - balance
        if abs(delta) < 0.005:
            self.status_var.set("CUADRADO")
            self.status_detail_var.set("El efectivo en caja coincide con el balance del día.")
            self.status_badge.configure(bg="#123F3B", fg=self.GREEN)
            self.add_log("Cuadre cuadrado: efectivo y balance coinciden.")
        elif delta > 0:
            self.status_var.set("SOBRANTE")
            self.status_detail_var.set(f"Hay un sobrante de {self._money(delta)} frente al balance.")
            self.status_badge.configure(bg="#44350F", fg=self.AMBER)
            self.add_log(f"Aviso: sobrante detectado de {self._money(delta)}.")
        else:
            self.status_var.set("FALTANTE")
            self.status_detail_var.set(f"Hay un faltante de {self._money(abs(delta))} frente al balance.")
            self.status_badge.configure(bg="#481C31", fg=self.RED)
            self.add_log(f"Aviso: faltante detectado de {self._money(abs(delta))}.")

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
            messagebox.showerror("Recibos", str(error), parent=self.master)

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
        self.add_log(f"Edición preparada para {description}. Actualice los campos y pulse «Actualizar seleccionado».")

    def update_selected_receipt(self) -> None:
        if not self.editing:
            messagebox.showinfo("Recibos", "Seleccione un recibo de la tabla para modificarlo.", parent=self.master)
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
            messagebox.showerror("Recibos", str(error), parent=self.master)

    def clear_receipt_form(self) -> None:
        self.editing = None
        self.beneficiario_var.set("")
        self.recibo_var.set("")
        self.valor_recibo_var.set("")
        for item in self.receipt_table.selection():
            self.receipt_table.selection_remove(item)

    def save_daily_data(self, *, show_success: bool = True):
        try:
            monthly = validate_non_negative_number(self.mensualidades_var.get(), "Mensualidades")
            other = validate_non_negative_number(self.varios_var.get(), "Ingresos varios")
            transfers = validate_non_negative_number(self.transferencias_var.get(), "Transferencias")
            cash = validate_non_negative_number(self.efectivo_var.get(), "Efectivo en caja")
            if any((self.beneficiario_var.get().strip(), self.recibo_var.get().strip(), self.valor_recibo_var.get().strip())):
                raise ValidationError("Añada o actualice el recibo que está en pantalla, o borre sus campos antes de guardar.")
            new_items = [(str(item["beneficiary"]), str(item["receipt"]), float(item["value"])) for item in self.new_receipts]
            changed_items = [(row, str(item["beneficiary"]), str(item["receipt"]), float(item["value"])) for row, item in self.updated_receipts.items()]
            path = save_daily_values(load_config(), monthly=monthly, other=other, transfers=transfers,
                                     cash=cash, new_receipts=new_items, updated_receipts=changed_items)
            for item in self.new_receipts:
                self.add_log(f"Recibo «{item['receipt']}» registrado correctamente.")
            for row in self.updated_receipts:
                self.add_log(f"Recibo de la fila {row} modificado correctamente.")
            self._load_saved_values()
            if show_success:
                messagebox.showinfo("Auto Cuadre", f"Cuadre guardado en:\n{path}", parent=self.master)
            return path
        except (ConfigurationError, ValidationError) as error:
            messagebox.showerror("Auto Cuadre", str(error), parent=self.master)
            self.add_log(f"No se guardó el cuadre: {error}")
        except Exception as error:
            messagebox.showerror("Auto Cuadre - Error", f"No se pudo guardar el cuadre:\n{error}", parent=self.master)
            self.add_log(f"Error no esperado al guardar: {error}")
        return None

    def show_print_menu(self) -> None:
        dialog = tk.Toplevel(self.master)
        dialog.title("Imprimir cuadre actual")
        dialog.resizable(False, False)
        dialog.transient(self.master)
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
        path = self.save_daily_data(show_success=False)
        if path:
            dialog.destroy()
            open_with_system(path)
            self.add_log("Cuadre abierto en Excel para impresión manual.")

    def _open_saved_for_print(self, dialog: tk.Toplevel) -> None:
        try:
            path = ensure_daily_workbook(load_config())
            dialog.destroy()
            open_with_system(path)
            self.add_log("Último cuadre guardado abierto en Excel.")
        except Exception as error:
            messagebox.showerror("Imprimir cuadre", f"No se pudo abrir el cuadre:\n{error}", parent=self.master)

    def _print_default(self, dialog: tk.Toplevel) -> None:
        if not messagebox.askyesno("Imprimir cuadre", "Se enviará el último cuadre guardado a la impresora predeterminada. ¿Desea continuar?", parent=dialog):
            return
        try:
            path = ensure_daily_workbook(load_config())
            open_with_system(path, "print")
            dialog.destroy()
            self.add_log("Cuadre enviado a la impresora predeterminada.")
        except Exception as error:
            messagebox.showerror("Imprimir cuadre", f"No se pudo enviar a imprimir:\n{error}", parent=self.master)


def main() -> None:
    root = tk.Tk()
    AutoCuadreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
