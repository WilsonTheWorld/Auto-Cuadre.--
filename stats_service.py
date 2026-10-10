"""Estadísticas por período: lectura rápida de los .xls, caché y avance mes a mes.

Por qué antes se congelaba: se abría Excel (COM) y cada archivo del período, uno por uno,
sin avance visible. Ahora:
  * Se leen E45/E47/E49 directo del .xls con xlrd (milisegundos por archivo, sin abrir Excel).
  * Si xlrd no está instalado se usa Excel, pero por lotes (un mes por llamada) con avance.
  * Los resultados se guardan en caché (ruta + fecha de modificación + tamaño): los meses
    cerrados casi nunca se vuelven a leer.
  * La carpeta de cada mes se lista una sola vez, no una vez por día.
"""

from __future__ import annotations

import calendar
import json
import os
import re
import threading
from datetime import date
from pathlib import Path
from typing import Any, Callable

from utils import (MONTHS, PROJECT_DIR, ConfigurationError, ValidationError,
                   _run_excel_automation, get_current_period_paths)

try:  # lectura directa de .xls, sin abrir Excel
    import xlrd
except ImportError:  # sin xlrd se usa Excel por lotes (más lento)
    xlrd = None

MAX_MONTHS = 12
CACHE_PATH = PROJECT_DIR / "stats_cache.json"
FILE_PATTERN = re.compile(r"^CUADRE CAJA (\d{2})-(\d{2})-(\d{4})\.xls$", re.IGNORECASE)
# Celdas del modelo (fila, columna) base 0: E45 balance, E47 efectivo, E49 diferencia
CELLS = {"balance": (44, 4), "cash": (46, 4), "difference": (48, 4)}

ProgressFn = Callable[..., None]


def reader_available() -> bool:
    return xlrd is not None


def month_label(year: int, month: int) -> str:
    return f"{MONTHS[month - 1].capitalize()} {year}"


def months_between(first: date, last: date) -> list[tuple[int, int]]:
    """Meses (año, mes) que toca el período. Máximo 12."""
    if last < first:
        raise ValidationError("La fecha final es anterior a la inicial.")
    months: list[tuple[int, int]] = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if len(months) > MAX_MONTHS:
        raise ValidationError(f"El rango máximo es de {MAX_MONTHS} meses (el elegido tiene {len(months)}).")
    return months


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def month_files(config: dict[str, Any], year: int, month: int, *, strict: bool = False) -> dict[date, Path]:
    """Cuadres existentes del mes (el directorio se lee una sola vez).

    strict=False: si la carpeta del mes no existe devuelve {}.
    strict=True : propaga ConfigurationError (para avisar al usuario de una carpeta faltante).
    """
    try:
        folder = get_current_period_paths(config, date(year, month, 1))["target_dir"]
    except ConfigurationError:
        if strict:
            raise
        return {}
    found: dict[date, Path] = {}
    with os.scandir(folder) as entries:
        for entry in entries:
            match = FILE_PATTERN.match(entry.name)
            if not match or not entry.is_file():
                continue  # también descarta los temporales ".CUADRE ... .tmp.xls"
            day, mon, yr = (int(group) for group in match.groups())
            if (yr, mon) != (year, month):
                continue
            try:
                found[date(yr, mon, day)] = Path(entry.path)
            except ValueError:
                continue
    return found


class StatsCache:
    """Caché en disco: ruta -> valores, válido mientras el archivo no cambie."""

    def __init__(self, path: Path | None = None) -> None:
        path = path or CACHE_PATH
        self.path, self.data, self.dirty = path, {}, False
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, json.JSONDecodeError):
            pass

    @staticmethod
    def _signature(file: Path) -> tuple[float, int]:
        stat = file.stat()
        return stat.st_mtime, stat.st_size

    def get(self, file: Path) -> dict[str, Any] | None:
        try:
            mtime, size = self._signature(file)
        except OSError:
            return None
        item = self.data.get(str(file))
        if item and item.get("mtime") == mtime and item.get("size") == size:
            return item.get("values")
        return None

    def put(self, file: Path, values: dict[str, Any]) -> None:
        try:
            mtime, size = self._signature(file)
        except OSError:
            return
        self.data[str(file)] = {"mtime": mtime, "size": size, "values": values}
        self.dirty = True

    def save(self) -> None:
        if not self.dirty:
            return
        try:
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(json.dumps(self.data), encoding="utf-8")
            os.replace(temporary, self.path)
        except OSError:
            pass  # la caché es opcional


def _cell(sheet, row: int, col: int) -> float | None:
    if row >= sheet.nrows or col >= sheet.ncols:
        return None
    cell = sheet.cell(row, col)
    return cell.value if cell.ctype == xlrd.XL_CELL_NUMBER else None  # vacío o error -> None


def read_values(file: Path) -> dict[str, float | None]:
    """Lee balance (E45), efectivo (E47) y diferencia (E49) directamente del .xls."""
    book = xlrd.open_workbook(str(file), on_demand=True, formatting_info=False)
    try:
        sheet = book.sheet_by_index(0)
        return {name: _cell(sheet, row, col) for name, (row, col) in CELLS.items()}
    finally:
        book.release_resources()


def _num(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _summarize(year: int, month: int, files_count: int, records: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in records if _num(r.get("balance")) is not None and _num(r.get("cash")) is not None]
    balance = sum(_num(r["balance"]) or 0 for r in valid)
    cash = sum(_num(r["cash"]) or 0 for r in valid)
    return {
        "key": (year, month), "label": month_label(year, month), "files": files_count,
        "days": len(valid), "balance": balance, "cash": cash, "difference": cash - balance,
        "squared": sum(1 for r in valid if abs(_num(r["balance"]) - _num(r["cash"])) < 0.005),
        "records": records,
    }


def compute_statistics(config: dict[str, Any], first_day: date, last_day: date,
                       progress: ProgressFn, cancel: threading.Event) -> dict[str, Any]:
    """Calcula el período mes por mes.

    progress(fracción, texto, datos) recibe:
      datos={"event": "month_start", "key": (año, mes)}  al empezar cada mes
      datos={"event": "month_done",  "summary": {...}}   al terminar cada mes
    """
    months = months_between(first_day, last_day)
    plan = []
    for year, month in months:
        files = {d: f for d, f in month_files(config, year, month).items() if first_day <= d <= last_day}
        plan.append((year, month, files))
    total = sum(len(files) for _, _, files in plan)
    cache, done, unreadable = StatsCache(), 0, 0
    all_records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    def fraction() -> float:
        return done / total if total else 1.0

    for year, month, files in plan:
        if cancel.is_set():
            break
        label = month_label(year, month)
        progress(fraction(), f"{label}: preparando…", {"event": "month_start", "key": (year, month)})
        records: list[dict[str, Any]] = []
        pending: list[date] = []
        for day in sorted(files):
            cached = cache.get(files[day])
            if cached is None:
                pending.append(day)
            else:
                records.append({"date": day.isoformat(), **cached})
                done += 1

        if pending and xlrd is not None:
            for day in pending:
                if cancel.is_set():
                    break
                try:
                    values = read_values(files[day])
                    cache.put(files[day], values)
                    records.append({"date": day.isoformat(), **values})
                except Exception:  # archivo dañado o bloqueado
                    unreadable += 1
                done += 1
                progress(fraction(), f"{label}: {done}/{total} cuadres", None)
        elif pending:  # sin xlrd: un lote de Excel por mes
            batch = [{"date": d.isoformat(), "path": str(files[d])} for d in pending]
            progress(fraction(), f"{label}: leyendo {len(batch)} cuadres con Excel…", None)
            try:
                rows = _run_excel_automation("statistics", None, {"records": batch}).get("records", [])
            except ConfigurationError:
                rows, unreadable = [], unreadable + len(batch)
            for row in rows:
                values = {name: row.get(name) for name in CELLS}
                cache.put(files[date.fromisoformat(row["date"])], values)
                records.append({"date": row["date"], **values})
            done += len(pending)

        if cancel.is_set():
            break
        records.sort(key=lambda r: r["date"])
        summary = _summarize(year, month, len(files), records)
        summaries.append(summary)
        all_records.extend(records)
        progress(fraction(), f"{label} calculado", {"event": "month_done", "summary": summary})

    cache.save()
    progress(1.0, "Listo", None)
    return {"records": all_records, "months": summaries, "unreadable": unreadable,
            "cancelled": cancel.is_set(), "engine": "xlrd" if xlrd is not None else "excel"}
