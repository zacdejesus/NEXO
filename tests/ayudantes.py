"""Shared helpers for the tests (not a test module)."""
from pathlib import Path

from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.modelos import ModeloReglas
from presentacion.chat_consola import ChatConsola
from servicios.agente import Agente

RAIZ = Path(__file__).resolve().parent.parent


def crear_agente(registro=None):
    return Agente(ModeloReglas(), [Calculadora(), ConversorMoneda(), BuscadorFAQ()], registro)


def ejecutar_chat(entradas, agente, repo=None, registro=None):
    """Runs ChatConsola with scripted input and returns everything it printed."""
    cola, salida = iter(entradas), []

    def entrada(_):
        try:
            return next(cola)
        except StopIteration:
            raise EOFError

    ChatConsola(agente, repo, registro, entrada=entrada, salida=salida.append).iniciar()
    return "\n".join(salida)
