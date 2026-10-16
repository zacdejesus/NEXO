import pytest

from dominio.excepciones import ErrorAgente, HerramientaNoEncontrada
from dominio.herramientas import Calculadora, ConversorMoneda
from dominio.mensaje import Conversacion
from dominio.modelos import Modelo, ModeloReglas, Respuesta
from servicios.agente import Agente
from tests.ayudantes import crear_agente


def test_herramienta_inexistente():
    class Raro(Modelo):
        def responder(self, conversacion, herramientas):
            return Respuesta(herramienta="no_existe")

    with pytest.raises(HerramientaNoEncontrada):
        Agente(Raro("raro"), [Calculadora()]).procesar("hola")


def test_limite_de_tres_iteraciones():
    llamadas = []

    class Bucle(Modelo):
        def responder(self, conversacion, herramientas):
            llamadas.append(1)
            return Respuesta(herramienta="calculadora", argumentos={"a": 1, "b": 1, "operacion": "+"})

    with pytest.raises(ErrorAgente):
        Agente(Bucle("bucle"), [Calculadora()]).procesar("hola")
    assert len(llamadas) == 3


def test_agente_sin_registro():
    agente = crear_agente(None)
    agente.procesar("3 * 79.9")
    assert len(agente.conversacion) == 3


# --- Reto 4: el bucle encadena dos herramientas -----------------------------

def test_encadena_dos_herramientas():
    agente = Agente(ModeloReglas(), [Calculadora(), ConversorMoneda()])
    respuesta = agente.procesar("convierte 100 USD a euros y multiplícalo por 3")
    assert respuesta == "Primero, 100 USD = 92.00 EUR; después, 92 * 3 = 276. ¿Necesitas algo más?"
    assert [nombre for nombre, _ in agente.herramientas_usadas] == ["conversor_moneda", "calculadora"]
    assert [m.rol for m in agente.conversacion.get_mensajes()] == \
        ["usuario", "herramienta", "herramienta", "asistente"]


def test_encadenar_sin_la_segunda_herramienta_falla():
    with pytest.raises(HerramientaNoEncontrada):
        Agente(ModeloReglas(), [ConversorMoneda()]).procesar("convierte 100 USD a euros y multiplícalo por 3")


# --- Reto 6: el agente sigue funcionando cuando la conversación se resume ---

def test_conversacion_larga_se_resume_sin_romperse():
    agente = crear_agente()
    agente.conversacion = Conversacion(limite_tokens=60)
    for _ in range(8):
        assert agente.procesar("cuánto es 3 * 4") == "El resultado es 3 * 4 = 12. ¿Necesitas algo más?"
    assert agente.conversacion.veces_resumida > 0
