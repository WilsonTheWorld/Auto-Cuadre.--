"""Lanzador para abrir el cuadre de la fecha actual en Excel."""

from tkinter import Tk, messagebox

from utils import ConfigurationError, ensure_daily_workbook, load_config, open_with_system


def main() -> None:
    root = Tk()
    root.withdraw()
    try:
        workbook = ensure_daily_workbook(load_config())
        open_with_system(workbook)
    except ConfigurationError as error:
        messagebox.showerror("Auto Cuadre - Configuración", str(error), parent=root)
    except Exception as error:
        messagebox.showerror("Auto Cuadre - Error", f"No se pudo abrir el cuadre:\n{error}", parent=root)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
