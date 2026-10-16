import json
import os
import re
from pathlib import Path

from dominio.excepciones import ErrorPersistencia
from dominio.mensaje import Conversacion


class RepositorioConversaciones:
    """Guarda cada conversación como <id>.json dentro de una carpeta."""

    _ID_VALIDO = re.compile(r"[A-Za-z0-9_-]+")

    def __init__(self, carpeta="datos/conversaciones"):
        self._carpeta = Path(carpeta)

    def _ruta(self, id_conv):
        if not isinstance(id_conv, str) or not self._ID_VALIDO.fullmatch(id_conv):
            raise ErrorPersistencia(f"Identificador no válido: {id_conv!r}")
        ruta = (self._carpeta / f"{id_conv}.json").resolve()
        if ruta.parent != self._carpeta.resolve():
            raise ErrorPersistencia(f"Identificador no válido: {id_conv!r}")
        return ruta

    def guardar(self, conversacion):
        ruta = self._ruta(conversacion.id)
        temporal = ruta.with_name(f".{ruta.name}.tmp")
        try:
            self._carpeta.mkdir(parents=True, exist_ok=True)
            with open(temporal, "w", encoding="utf-8") as f:
                json.dump(conversacion.to_dict(), f, ensure_ascii=False, indent=2)
            os.replace(temporal, ruta)
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo guardar la conversación: {e}") from e

    def cargar(self, id_conv) -> Conversacion:
        ruta = self._ruta(id_conv)
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except FileNotFoundError as e:
            raise ErrorPersistencia(f"No existe la conversación '{id_conv}'") from e
        except ValueError as e:  # JSON corrupto o codificación errónea
            raise ErrorPersistencia(f"El archivo de '{id_conv}' está corrupto") from e
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo leer la conversación '{id_conv}': {e}") from e
        try:
            return Conversacion.from_dict(datos)
        except (ValueError, TypeError) as e:
            raise ErrorPersistencia(f"La conversación '{id_conv}' no es válida: {e}") from e

    def listar(self) -> list[str]:
        try:
            if not self._carpeta.is_dir():
                return []
            return sorted(
                p.stem
                for p in self._carpeta.iterdir()
                if p.is_file() and p.suffix == ".json" and self._ID_VALIDO.fullmatch(p.stem)
            )
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo listar las conversaciones: {e}") from e
