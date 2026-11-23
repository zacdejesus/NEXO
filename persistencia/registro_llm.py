import csv
import os
from datetime import datetime

from dominio.excepciones import ErrorPersistencia


class RegistroLLM:
    """Anota cada llamada al modelo Claude en un CSV: fecha, pregunta, tokens de salida y coste.

    El coste se calcula con los precios por millón de tokens de Claude Haiku 5.5 (hasta 100 000
    tokens por petición), en dólares. Si cambian los precios, hay que actualizar las dos constantes.
    """

    PRECIO_ENTRADA_POR_MTOK = 0.10  # USD por millón de tokens de entrada
    PRECIO_SALIDA_POR_MTOK = 0.50   # USD por millón de tokens de salida
    CABECERA = ["timestamp", "question", "output_tokens", "cost"]

    # Recibe la ruta del CSV. Por defecto se guarda en datos/uso_llm.csv.
    def __init__(self, ruta="datos/uso_llm.csv"):
        self._ruta = ruta

    # Añade una fila y devuelve el coste de la llamada. Crea el CSV con cabecera si no existe.
    def registrar(self, pregunta, tokens_entrada, tokens_salida) -> float:
        coste = (tokens_entrada * self.PRECIO_ENTRADA_POR_MTOK
                 + tokens_salida * self.PRECIO_SALIDA_POR_MTOK) / 1_000_000
        try:
            carpeta = os.path.dirname(self._ruta)
            if carpeta:
                os.makedirs(carpeta, exist_ok=True)
            nuevo = not os.path.exists(self._ruta) or os.path.getsize(self._ruta) == 0
            with open(self._ruta, "a", newline="", encoding="utf-8") as f:
                escritor = csv.writer(f)
                if nuevo:
                    escritor.writerow(self.CABECERA)
                escritor.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    pregunta,
                    tokens_salida,
                    f"{coste:.6f}",
                ])
        except OSError as e:
            raise ErrorPersistencia(f"No se pudo escribir el registro de uso: {e}") from e
        return coste
