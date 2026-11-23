import json

import pytest

from dominio.herramientas import Calculadora
from dominio.mensaje import Conversacion, Mensaje
from dominio.modelos import ModeloLLM
from servicios.cliente_llm import ClienteLLM


def test_lee_url_y_modelo_de_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("NEXO_LLM_URL", "http://127.0.0.1:8080/v1/")
    monkeypatch.setenv("NEXO_LLM_MODELO", "mlx-community/gemma-4-12B-it-4bit")
    cliente = ClienteLLM()
    assert cliente._url == "http://127.0.0.1:8080/v1/chat/completions"
    assert cliente._modelo == "mlx-community/gemma-4-12B-it-4bit"


def test_argumentos_explicitos_pesan_mas_que_el_entorno(monkeypatch):
    monkeypatch.setenv("NEXO_LLM_URL", "http://otro:1/v1")
    monkeypatch.setenv("NEXO_LLM_MODELO", "otro")
    cliente = ClienteLLM(modelo="mi-modelo", url_base="http://127.0.0.1:9/v1")
    assert cliente._url == "http://127.0.0.1:9/v1/chat/completions"
    assert cliente._modelo == "mi-modelo"


def test_sin_entorno_usa_ollama_por_defecto(monkeypatch):
    monkeypatch.delenv("NEXO_LLM_URL", raising=False)
    monkeypatch.delenv("NEXO_LLM_MODELO", raising=False)
    cliente = ClienteLLM()
    assert cliente._url == "http://localhost:11434/v1/chat/completions"
    assert cliente._modelo == ClienteLLM.MODELO_POR_DEFECTO


class ClienteFijo:
    def __init__(self, texto):
        self.texto = texto

    def completar(self, mensajes):
        return self.texto


def _conversacion():
    conversacion = Conversacion()
    conversacion.agregar(Mensaje("usuario", "hola"))
    return conversacion


@pytest.mark.parametrize("texto", ["", "   ", json.dumps({"respuesta": ""}), json.dumps({"respuesta": "  "})])
def test_respuesta_vacia_da_aviso_en_vez_de_linea_en_blanco(texto):
    respuesta = ModeloLLM(ClienteFijo(texto)).responder(_conversacion(), [Calculadora()])
    assert not respuesta.es_llamada_herramienta()
    assert respuesta.texto.startswith("No he podido generar una respuesta")
