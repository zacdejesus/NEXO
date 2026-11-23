import json

import pytest

from dominio.herramientas import BuscadorFAQ, Calculadora, ConversorMoneda
from dominio.mensaje import Conversacion, Mensaje
from dominio.modelos import ModeloLLM


class ClienteFalso:
    """Imita al cliente HTTP: guarda lo que recibe y devuelve una respuesta fija."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.mensajes = None

    def completar(self, mensajes):
        self.mensajes = mensajes
        return self.respuesta


def _conversacion(*mensajes):
    conversacion = Conversacion()
    for rol, contenido in mensajes:
        conversacion.agregar(Mensaje(rol, contenido))
    return conversacion


HERRAMIENTAS = [Calculadora(), ConversorMoneda(), BuscadorFAQ()]


def test_respuesta_de_texto():
    cliente = ClienteFalso(json.dumps({"respuesta": "¡Hola! ¿En qué te ayudo?"}))
    respuesta = ModeloLLM(cliente).responder(_conversacion(("usuario", "hola")), HERRAMIENTAS)
    assert not respuesta.es_llamada_herramienta()
    assert respuesta.texto == "¡Hola! ¿En qué te ayudo?"


def test_pide_herramienta_con_argumentos():
    cliente = ClienteFalso('{"herramienta": "calculadora", "argumentos": {"a": 3, "b": 79.9, "operacion": "*"}}')
    respuesta = ModeloLLM(cliente).responder(_conversacion(("usuario", "3 por 79,90")), HERRAMIENTAS)
    assert respuesta.es_llamada_herramienta()
    assert respuesta.herramienta == "calculadora"
    assert respuesta.argumentos == {"a": 3, "b": 79.9, "operacion": "*"}


def test_json_rodeado_de_texto():
    cliente = ClienteFalso('Claro, aquí tienes: {"respuesta": "Envíos en 24-48 h."} ¡Un saludo!')
    respuesta = ModeloLLM(cliente).responder(_conversacion(("usuario", "envíos")), HERRAMIENTAS)
    assert respuesta.texto == "Envíos en 24-48 h."


@pytest.mark.parametrize("salida", [
    "Esto no es JSON, es texto libre.",
    '{"herramienta": "calculadora", "argumentos": [1, 2]}',  # argumentos mal formados
    '{"herramienta": "calculadora", "argumentos": {"a": 1}',  # JSON cortado
    '{"otra_clave": 1}',
])
def test_si_no_entiende_el_json_devuelve_el_texto(salida):
    respuesta = ModeloLLM(ClienteFalso(salida)).responder(_conversacion(("usuario", "hola")), HERRAMIENTAS)
    assert not respuesta.es_llamada_herramienta()
    assert respuesta.texto == salida.strip()


def test_envia_prompt_de_sistema_con_las_herramientas():
    cliente = ClienteFalso('{"respuesta": "ok"}')
    ModeloLLM(cliente).responder(_conversacion(("usuario", "hola")), HERRAMIENTAS)
    sistema = cliente.mensajes[0]
    assert sistema["role"] == "system"
    for nombre in ("calculadora", "conversor_moneda", "buscador_faq"):
        assert nombre in sistema["content"]
    assert "JSON" in sistema["content"]


def test_traduce_roles_y_resultados_de_herramienta():
    cliente = ClienteFalso('{"respuesta": "ok"}')
    conversacion = _conversacion(
        ("usuario", "3 * 4"),
        ("asistente", "Voy a calcularlo"),
        ("herramienta", "3 * 4 = 12"),
    )
    ModeloLLM(cliente).responder(conversacion, HERRAMIENTAS)
    enviados = cliente.mensajes[1:]
    assert enviados[0] == {"role": "user", "content": "3 * 4"}
    assert enviados[1] == {"role": "assistant", "content": "Voy a calcularlo"}
    assert enviados[2] == {"role": "user", "content": "Resultado de la herramienta: 3 * 4 = 12"}


def test_nombre_por_defecto():
    assert ModeloLLM(ClienteFalso("{}")).nombre == "llm"
