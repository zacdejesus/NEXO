"""Ejercicio 4: hace las mismas 10 preguntas a ModeloReglas y a ModeloClaude, y guarda las
respuestas y los tiempos en listas para compararlas.

Ejecución (desde la raíz del proyecto, con LLM_API_KEY en .env):
    python comparar_modelos.py
"""
import time

from dominio.excepciones import ErrorAgente
from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.modelos import ModeloClaude, ModeloReglas
from persistencia.registro_llm import RegistroLLM
from servicios.agente import Agente
from servicios.cliente_anthropic import ClienteAnthropic

PREGUNTAS = [
    "hola",
    "¿cuánto tarda el envío?",
    "¿cuánto son 250 dólares en euros?",
    "si compro 3 SSD a 79,90 euros, ¿cuánto pago?",
    "¿puedo devolver un producto?",
    "¿qué formas de pago aceptáis?",
    "¿a qué hora abrís?",
    "cuánto es 12 por 7",
    "¿me recomiendas una gráfica para jugar?",
    "quiero hablar con una persona",
]


# Herramientas nuevas en cada ejecución, para que ningún modelo herede el contexto del anterior.
def herramientas():
    return [Calculadora(), ConversorMoneda(), BuscadorFAQ()]


# Hace todas las preguntas con un modelo y devuelve las respuestas y los segundos que tardó cada una.
def ejecutar(modelo):
    respuestas, tiempos = [], []
    for pregunta in PREGUNTAS:
        agente = Agente(modelo, herramientas(), None)  # conversación nueva para cada pregunta
        inicio = time.perf_counter()
        try:
            respuesta = agente.procesar(pregunta)
        except ErrorAgente as e:
            respuesta = f"ERROR: {e}"
        tiempos.append(round(time.perf_counter() - inicio, 2))
        respuestas.append(respuesta)
    return respuestas, tiempos


if __name__ == "__main__":
    respuestas_reglas, tiempos_reglas = ejecutar(ModeloReglas())
    modelo_claude = ModeloClaude(ClienteAnthropic(registro=RegistroLLM()))
    respuestas_claude, tiempos_claude = ejecutar(modelo_claude)

    for i, pregunta in enumerate(PREGUNTAS):
        print(f"\n{i + 1}. {pregunta}")
        print(f"   reglas ({tiempos_reglas[i]} s): {respuestas_reglas[i]}")
        print(f"   claude ({tiempos_claude[i]} s): {respuestas_claude[i]}")
