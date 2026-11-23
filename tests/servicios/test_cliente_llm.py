import json
import urllib.error

import pytest

from dominio.excepciones import ErrorAgente, ErrorModelo
from servicios import cliente_llm
from servicios.cliente_llm import ClienteLLM


class RespuestaFalsa:
    """Imita la respuesta HTTP que devuelve urlopen() como gestor de contexto."""

    def __init__(self, cuerpo):
        self._cuerpo = cuerpo

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _respuesta_api(contenido):
    return json.dumps({"choices": [{"message": {"role": "assistant", "content": contenido}}]}).encode()


def test_envia_peticion_y_lee_el_texto(monkeypatch):
    capturado = {}

    def urlopen_falso(peticion, timeout):
        capturado["url"] = peticion.full_url
        capturado["cuerpo"] = json.loads(peticion.data.decode())
        capturado["timeout"] = timeout
        return RespuestaFalsa(_respuesta_api('{"respuesta": "hola"}'))

    monkeypatch.setattr(cliente_llm.urllib.request, "urlopen", urlopen_falso)
    cliente = ClienteLLM(modelo="mi-modelo", url_base="http://localhost:1234/v1/", timeout=5)

    texto = cliente.completar([{"role": "user", "content": "hola"}])

    assert texto == '{"respuesta": "hola"}'
    assert capturado["url"] == "http://localhost:1234/v1/chat/completions"
    assert capturado["cuerpo"]["model"] == "mi-modelo"
    assert capturado["cuerpo"]["stream"] is False
    assert capturado["cuerpo"]["messages"] == [{"role": "user", "content": "hola"}]
    assert capturado["timeout"] == 5


def test_servidor_apagado_lanza_error_modelo(monkeypatch):
    def urlopen_roto(peticion, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(cliente_llm.urllib.request, "urlopen", urlopen_roto)
    with pytest.raises(ErrorModelo, match="No puedo conectar"):
        ClienteLLM().completar([])


def test_error_http_lanza_error_modelo_con_el_codigo(monkeypatch):
    def urlopen_404(peticion, timeout):
        raise urllib.error.HTTPError(peticion.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(cliente_llm.urllib.request, "urlopen", urlopen_404)
    with pytest.raises(ErrorModelo, match="404"):
        ClienteLLM().completar([])


def test_respuesta_que_no_es_json_lanza_error_modelo(monkeypatch):
    monkeypatch.setattr(cliente_llm.urllib.request, "urlopen",
                        lambda peticion, timeout: RespuestaFalsa(b"<html>ups</html>"))
    with pytest.raises(ErrorModelo):
        ClienteLLM().completar([])


def test_respuesta_sin_choices_lanza_error_modelo(monkeypatch):
    monkeypatch.setattr(cliente_llm.urllib.request, "urlopen",
                        lambda peticion, timeout: RespuestaFalsa(b'{"otra": 1}'))
    with pytest.raises(ErrorModelo):
        ClienteLLM().completar([])


def test_error_modelo_es_error_agente():
    assert issubclass(ErrorModelo, ErrorAgente)
