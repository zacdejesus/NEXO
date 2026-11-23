"""Pruebas del modelo Claude con unittest. Se ejecutan con: python -m unittest test_modelo.py

No hacen llamadas reales a la API: la red se sustituye por respuestas falsas.
"""
import csv
import json
import os
import tempfile
import unittest
from unittest import mock

import httpx

from dominio.excepciones import ErrorModelo, PeticionInvalida
from dominio.herramientas import Calculadora
from dominio.mensaje import Conversacion, Mensaje
from dominio.modelos import ModeloClaude
from persistencia.registro_llm import RegistroLLM
from servicios.cliente_anthropic import ClienteAnthropic


def eventos_sse(*eventos):
    return [f"data: {json.dumps(evento)}" for evento in eventos]


# Respuesta correcta de la API en streaming: dos fragmentos de texto, 1000 tokens de entrada
# y 2000 de salida.
RESPUESTA_TEXTO = eventos_sse(
    {"type": "message_start", "message": {"usage": {"input_tokens": 1000, "output_tokens": 1}}},
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hola "}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "cliente"}},
    {"type": "content_block_stop", "index": 0},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2000}},
    {"type": "message_stop"},
)


class RespuestaFalsa:
    """Imita la respuesta HTTP en streaming: código de estado, líneas y close()."""

    def __init__(self, status=200, lineas=()):
        self.status_code = status
        self._lineas = list(lineas)
        self.cerrada = False

    def iter_lines(self):
        return iter(self._lineas)

    def read(self):
        return b""

    def close(self):
        self.cerrada = True


class HttpFalso:
    """Sustituye al cliente httpx: devuelve las respuestas en orden y cuenta las peticiones."""

    def __init__(self, respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = 0

    def build_request(self, *args, **kwargs):
        return None

    def send(self, peticion, stream):
        indice = min(self.llamadas, len(self._respuestas) - 1)
        self.llamadas += 1
        return self._respuestas[indice]


def cliente_con(respuestas, **opciones):
    cliente = ClienteAnthropic(api_key="clave-de-prueba", **opciones)
    cliente._http = HttpFalso(respuestas)
    return cliente


MENSAJE_USUARIO = [{"role": "user", "content": "hola"}]


class TestValidacion(unittest.TestCase):

    def test_mensaje_vacio_lanza_excepcion(self):
        with self.assertRaises(PeticionInvalida):
            cliente_con([RespuestaFalsa()]).completar([])

    def test_primer_mensaje_debe_ser_del_usuario(self):
        mensajes = [{"role": "assistant", "content": "hola"}]
        with self.assertRaises(PeticionInvalida):
            cliente_con([RespuestaFalsa()]).completar(mensajes)

    def test_rol_no_valido(self):
        mensajes = [{"role": "user", "content": "hola"}, {"role": "sistema", "content": "x"}]
        with self.assertRaises(PeticionInvalida):
            cliente_con([RespuestaFalsa()]).completar(mensajes)

    def test_max_tokens_debe_ser_positivo(self):
        with self.assertRaises(PeticionInvalida):
            cliente_con([RespuestaFalsa()], max_tokens=0).completar(MENSAJE_USUARIO)

    def test_temperatura_fuera_de_rango(self):
        with self.assertRaises(PeticionInvalida):
            cliente_con([RespuestaFalsa()], temperatura=3).completar(MENSAJE_USUARIO)

    def test_sin_clave_avisa_antes_de_llamar(self):
        with mock.patch("servicios.cliente_anthropic.load_dotenv"), \
                mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ErrorModelo):
                ClienteAnthropic()


class TestRegistroCSV(unittest.TestCase):

    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        self.ruta = os.path.join(self.carpeta, "uso_llm.csv")

    def test_escribe_cabecera_y_fila_con_tokens_y_coste(self):
        cliente = cliente_con([RespuestaFalsa(lineas=RESPUESTA_TEXTO)],
                              registro=RegistroLLM(self.ruta))
        datos = cliente.completar(MENSAJE_USUARIO)

        self.assertEqual(datos["texto"], "Hola cliente")
        with open(self.ruta, encoding="utf-8") as f:
            filas = list(csv.reader(f))
        self.assertEqual(filas[0], ["timestamp", "question", "output_tokens", "cost"])
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[1][1], "hola")
        self.assertEqual(filas[1][2], "2000")
        # 1000 tokens de entrada a 0,10 USD/millón + 2000 de salida a 0,50 USD/millón = 0,0011 USD
        self.assertEqual(filas[1][3], "0.001100")

    def test_no_repite_la_cabecera_en_la_segunda_llamada(self):
        registro = RegistroLLM(self.ruta)
        cliente = cliente_con([RespuestaFalsa(lineas=RESPUESTA_TEXTO)], registro=registro)
        cliente.completar(MENSAJE_USUARIO)
        cliente._http = HttpFalso([RespuestaFalsa(lineas=RESPUESTA_TEXTO)])
        cliente.completar(MENSAJE_USUARIO)
        with open(self.ruta, encoding="utf-8") as f:
            filas = list(csv.reader(f))
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[0][0], "timestamp")


class TestReintentos(unittest.TestCase):

    def setUp(self):
        # Sin esperas reales entre reintentos.
        patch = mock.patch("time.sleep")
        patch.start()
        self.addCleanup(patch.stop)

    def test_429_se_reintenta_cinco_veces_y_luego_falla(self):
        cliente = cliente_con([RespuestaFalsa(status=429)])
        with self.assertRaises(ErrorModelo):
            cliente.completar(MENSAJE_USUARIO)
        self.assertEqual(cliente._http.llamadas, 5)

    def test_5xx_se_reintenta_y_luego_funciona(self):
        cliente = cliente_con([RespuestaFalsa(status=500), RespuestaFalsa(lineas=RESPUESTA_TEXTO)])
        datos = cliente.completar(MENSAJE_USUARIO)
        self.assertEqual(datos["texto"], "Hola cliente")
        self.assertEqual(cliente._http.llamadas, 2)

    def test_400_no_se_reintenta(self):
        cliente = cliente_con([RespuestaFalsa(status=400)])
        with self.assertRaises(ErrorModelo):
            cliente.completar(MENSAJE_USUARIO)
        self.assertEqual(cliente._http.llamadas, 1)


class TestStreaming(unittest.TestCase):

    def test_cada_fragmento_llega_al_momento(self):
        fragmentos = []
        cliente = cliente_con([RespuestaFalsa(lineas=RESPUESTA_TEXTO)], al_fragmento=fragmentos.append)
        cliente.completar(MENSAJE_USUARIO)
        self.assertEqual(fragmentos, ["Hola ", "cliente"])


class TestHerramientasYConversacion(unittest.TestCase):

    def test_esquema_de_la_calculadora(self):
        esquema = Calculadora().esquema()
        self.assertEqual(esquema["name"], "calculadora")
        self.assertIn("operacion", esquema["input_schema"]["required"])

    def test_traduce_conversacion_a_la_api(self):
        conversacion = Conversacion()
        conversacion.agregar(Mensaje("asistente", "Hola, ¿en qué ayudo?"))  # la API exige empezar por el usuario: se descarta
        conversacion.agregar(Mensaje("usuario", "3 por 4"))
        conversacion.agregar(Mensaje("herramienta", "3 * 4 = 12"))
        api = ModeloClaude._a_api(conversacion.get_mensajes())
        self.assertEqual(api[0]["role"], "user")
        self.assertEqual(api[0]["content"], "3 por 4\nResultado de la herramienta: 3 * 4 = 12")
        self.assertEqual(len(api), 1)


if __name__ == "__main__":
    unittest.main()
