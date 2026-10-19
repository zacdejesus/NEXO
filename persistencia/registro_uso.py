import csv
from datetime import datetime
from pathlib import Path

from dominio.excepciones import ErrorPersistencia


class RegistroUso:
    """Registro CSV de cada ejecución de herramienta."""

    COLUMNAS = ["fecha", "herramienta", "argumentos", "exito", "milisegundos"]

    # Guarda la ruta del archivo CSV.
    def __init__(self, ruta="datos/uso.csv"):
        self._ruta = Path(ruta)

    # Añade una fila al CSV (y la cabecera si el archivo está vacío).
    def registrar(self, herramienta, argumentos, exito, milisegundos):
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            hay_cabecera = self._ruta.exists() and self._ruta.stat().st_size > 0
            with open(self._ruta, "a", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                if not hay_cabecera:
                    escritor.writerow(self.COLUMNAS)
                escritor.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    herramienta,
                    str(argumentos),
                    bool(exito),
                    round(milisegundos, 2),
                ])
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo escribir el registro de uso: {e}") from e

    # Lee el CSV y cuenta los usos y fallos de cada herramienta.
    def resumen(self) -> dict:
        resumen = {"total": 0, "usos": {}, "fallos": {}}
        if not self._ruta.exists():
            return resumen
        try:
            with open(self._ruta, "r", newline="", encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    herramienta = fila.get("herramienta")
                    if not herramienta:
                        continue
                    resumen["total"] += 1
                    resumen["usos"][herramienta] = resumen["usos"].get(herramienta, 0) + 1
                    resumen["fallos"].setdefault(herramienta, 0)
                    if fila.get("exito") != "True":
                        resumen["fallos"][herramienta] += 1
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            raise ErrorPersistencia(f"No se pudo leer el registro de uso: {e}") from e
        return resumen
