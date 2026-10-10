"""Detecta cuadres faltantes del mes en curso según los días laborables configurados."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from stats_service import month_files
from ui_helpers import spanish_date


def format_day(day: date) -> str:
    return spanish_date(day)


def find_missing_cuadres(config: dict[str, Any], today: date | None = None) -> list[date]:
    """Días laborables del mes (hasta hoy) sin archivo de cuadre.

    Reglas (configurables en Configuración):
      * workdays: días de la semana que se labora (0 = lunes … 6 = domingo). Por defecto lunes a sábado.
      * holidays: fechas "AAAA-MM-DD" que no se laboran.
      * alert_today: si es False, el día de hoy no se avisa (útil si el cuadre se hace al cierre).
    Lanza ConfigurationError si falta la carpeta del mes.
    """
    today = today or date.today()
    workdays = set(config.get("workdays", [0, 1, 2, 3, 4, 5]))
    holidays = set(config.get("holidays", []))
    include_today = bool(config.get("alert_today", True))
    existing = month_files(config, today.year, today.month, strict=True)
    last = today if include_today else today - timedelta(days=1)
    missing: list[date] = []
    day = today.replace(day=1)
    while day <= last:
        if day.weekday() in workdays and day.isoformat() not in holidays and day not in existing:
            missing.append(day)
        day += timedelta(days=1)
    return missing
