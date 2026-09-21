"""Operaciones de archivos, validación y automatización de Excel para Auto Cuadre."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"
MONTHS = (
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
)
OLE_HEADER = bytes.fromhex("D0CF11E0A1B11AE1")


class ConfigurationError(RuntimeError):
    """La estructura de archivos no permite crear o abrir un cuadre."""


class ValidationError(ValueError):
    """Un dato introducido no satisface las reglas de negocio."""


def load_config() -> dict[str, str]:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"No se pudo leer {CONFIG_PATH.name}: {error}") from error
    if not isinstance(config, dict):
        raise ConfigurationError("config.json debe contener un objeto JSON.")
    return {
        "template_path": str(config.get("template_path", "")).strip(),
        "base_dir": str(config.get("base_dir", "")).strip(),
    }


def _find_existing_directory(parent: Path, expected_name: str, *, prefix: bool = False) -> Path | None:
    """Busca una carpeta existente sin crear ni renombrar nada."""
    if not parent.is_dir():
        return None
    expected = expected_name.casefold()
    for item in parent.iterdir():
        if not item.is_dir():
            continue
        name = item.name.casefold()
        if name == expected or (prefix and name.startswith(expected + " ")):
            return item
    return None


def ensure_configuration(config: dict[str, str]) -> tuple[Path, Path]:
    template = Path(config["template_path"]).expanduser()
    base_dir = Path(config["base_dir"]).expanduser()
    if not template.is_file() or template.suffix.lower() != ".xls":
        raise ConfigurationError("No se encontró el modelo .xls configurado.")
    if not base_dir.is_dir():
        raise ConfigurationError("No se encontró la carpeta principal configurada.")
    return template, base_dir


def get_current_period_paths(config: dict[str, str], today: date | None = None) -> dict[str, Path]:
    """Ubica exclusivamente las carpetas existentes del centro; nunca crea carpetas."""
    _, base_dir = ensure_configuration(config)
    today = today or date.today()
    year_name = f"CUADRE {today.year}"
    year_dir = _find_existing_directory(base_dir, year_name)
    if year_dir is None:
        raise ConfigurationError(f"No existe la carpeta requerida «{year_name}». No se creará automáticamente.")
    month_name = MONTHS[today.month - 1]
    month_dir = _find_existing_directory(year_dir, month_name, prefix=True)
    if month_dir is None:
        raise ConfigurationError(f"No existe la carpeta requerida «{month_name}» dentro de {year_name}. No se creará automáticamente.")
    filename = f"CUADRE CAJA {today:%d-%m-%Y}.xls"
    return {"target_dir": month_dir, "target_filepath": month_dir / filename}


def is_valid_legacy_workbook(filepath: Path | str) -> bool:
    filepath = Path(filepath)
    try:
        return filepath.is_file() and filepath.read_bytes()[:8] == OLE_HEADER
    except OSError:
        return False


def ensure_daily_workbook(config: dict[str, str], today: date | None = None) -> Path:
    """Crea solo el archivo del día dentro de la carpeta del mes ya existente."""
    template, _ = ensure_configuration(config)
    paths = get_current_period_paths(config, today)
    filepath = paths["target_filepath"]
    if filepath.exists():
        if not is_valid_legacy_workbook(filepath):
            raise ConfigurationError(
                f"El archivo existente «{filepath.name}» no es un Excel .xls válido. No fue modificado."
            )
        return filepath

    temporary = filepath.with_name(f".{filepath.stem}.{uuid.uuid4().hex}.tmp.xls")
    try:
        shutil.copy2(template, temporary)
        _run_excel_automation("initialize", temporary, {"date": (today or date.today()).strftime("%d/%m/%Y")})
        if not is_valid_legacy_workbook(temporary):
            raise ConfigurationError("Excel no generó un archivo .xls válido.")
        os.replace(temporary, filepath)
    finally:
        if temporary.exists():
            temporary.unlink()
    return filepath


def read_daily_values(config: dict[str, str]) -> dict[str, Any] | None:
    """Lee valores existentes sin crear un archivo diario nuevo."""
    filepath = get_current_period_paths(config)["target_filepath"]
    if not filepath.exists():
        return None
    if not is_valid_legacy_workbook(filepath):
        raise ConfigurationError(f"El archivo existente «{filepath.name}» no es un Excel .xls válido.")
    return _run_excel_automation("read", filepath, {})


def get_statistics(config: dict[str, str], period: str, today: date | None = None) -> list[dict[str, Any]]:
    """Obtiene comparaciones de archivos existentes para una semana, mes o año."""
    today = today or date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
    else:
        raise ValidationError("El período de estadísticas no es válido.")

    records: list[dict[str, str]] = []
    cursor = start
    while cursor <= today:
        try:
            filepath = get_current_period_paths(config, cursor)["target_filepath"]
        except ConfigurationError:
            cursor += timedelta(days=1)
            continue
        if filepath.exists() and is_valid_legacy_workbook(filepath):
            records.append({"date": cursor.isoformat(), "path": str(filepath)})
        cursor += timedelta(days=1)
    if not records:
        return []
    result = _run_excel_automation("statistics", None, {"records": records})
    return list(result.get("records", []))


def save_daily_values(config: dict[str, str], *, monthly: float, other: float,
                      transfers: float, cash: float,
                      new_receipts: list[tuple[str, str, float]],
                      updated_receipts: list[tuple[int, str, str, float]]) -> tuple[Path, dict[str, Any]]:
    filepath = ensure_daily_workbook(config)
    payload = {
        "monthly": monthly,
        "other": other,
        "transfers": transfers,
        "cash": cash,
        "newReceipts": [
            {"beneficiary": beneficiary, "receipt": receipt, "value": value}
            for beneficiary, receipt, value in new_receipts
        ],
        "updates": [
            {"row": row, "beneficiary": beneficiary, "receipt": receipt, "value": value}
            for row, beneficiary, receipt, value in updated_receipts
        ],
    }
    values = _run_excel_automation("update", filepath, payload)
    return filepath, values


def _run_excel_automation(action: str, filepath: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    """Automatiza Microsoft Excel para mantener intacto el formato .xls institucional."""
    script = PROJECT_DIR / "excel_automation.ps1"
    if not script.is_file():
        raise ConfigurationError("No se encontró el componente de automatización de Excel.")
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-File", str(script),
               "-Action", action, "-PayloadBase64", encoded]
    if filepath is not None:
        command.extend(["-WorkbookPath", str(filepath)])
    process = subprocess.run(
        command,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip() or "Microsoft Excel no pudo procesar el archivo."
        raise ConfigurationError(f"No se pudo procesar el cuadre en Microsoft Excel: {detail}")
    if action not in {"read", "update", "statistics"}:
        return {}
    try:
        return json.loads(process.stdout.strip())
    except json.JSONDecodeError as error:
        raise ConfigurationError("Microsoft Excel devolvió una lectura no válida del cuadre.") from error


def validate_non_negative_number(value: Any, field_name: str = "El monto", *, positive: bool = False) -> float:
    normalized = str(value).strip().replace(" ", "").replace("$", "")
    if not normalized:
        raise ValidationError(f"{field_name} es obligatorio.")
    if normalized.count(",") == 1 and normalized.count(".") >= 1:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")
    try:
        number = Decimal(normalized)
    except InvalidOperation as error:
        raise ValidationError(f"{field_name} debe ser un número válido.") from error
    if not number.is_finite() or number < 0 or (positive and number == 0):
        operator = "mayor que cero" if positive else "igual o mayor que cero"
        raise ValidationError(f"{field_name} debe ser {operator}.")
    return float(number)


def open_with_system(filepath: Path, action: str = "open") -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(filepath), action)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(filepath)])
    else:
        subprocess.Popen(["xdg-open", str(filepath)])
