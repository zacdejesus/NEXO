import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from dominio.excepciones import ErrorModelo, PeticionInvalida

# La clave se lee de .env (LLM_API_KEY), que está en la raíz del proyecto y no se sube a git.
RAIZ = Path(__file__).resolve().parent.parent


# Reintenta solo los errores que pueden desaparecer: límite de peticiones (429) y fallos del servidor (5xx).
def _es_reintentable(error):
    if isinstance(error, httpx.HTTPStatusError):
        codigo = error.response.status_code
        return codigo == 429 or codigo >= 500
    return False


class ClienteAnthropic:
    """Llama a la API de Anthropic (Claude) en streaming.

    Usa httpx para la red y tenacity para los reintentos. Cada fragmento de texto se entrega
    a al_fragmento en cuanto llega, y las llamadas se anotan en registro (RegistroLLM).
    """

    URL = "https://api.anthropic.com/v1/messages"
    VERSION_API = "2023-06-01"
    MODELO_POR_DEFECTO = "claude-haiku-5-5"

    # Guarda la clave, el modelo, los límites y, si se pasan, la función que muestra los fragmentos
    # y el registro de uso.
    # La temperatura es opcional: Claude Haiku 5.5 no la acepta, así que por defecto no se envía.
    def __init__(self, api_key=None, modelo=None, max_tokens=512, temperatura=None,
                 al_fragmento=None, registro=None, timeout=60):
        load_dotenv(RAIZ / ".env")
        clave = api_key or os.getenv("LLM_API_KEY")
        if not clave or clave == "tu_clave_aqui":
            raise ErrorModelo("Falta la clave de Anthropic: pon LLM_API_KEY=... en el archivo .env")
        self._clave = clave
        self._modelo = modelo or self.MODELO_POR_DEFECTO
        self._max_tokens = max_tokens
        self._temperatura = temperatura
        self._al_fragmento = al_fragmento
        self._registro = registro
        self._http = httpx.Client(timeout=timeout)

    # Envía la conversación y devuelve un diccionario con el texto o la herramienta pedida,
    # y los tokens usados.
    def completar(self, mensajes, herramientas=None, system=None) -> dict:
        self._validar(mensajes)
        payload = {
            "model": self._modelo,
            "max_tokens": self._max_tokens,
            "messages": mensajes,
            "stream": True,
        }
        if self._temperatura is not None:
            payload["temperature"] = self._temperatura
        if system:
            payload["system"] = system
        if herramientas:
            payload["tools"] = herramientas
        try:
            respuesta = self._abrir(payload)
        except httpx.HTTPStatusError as e:
            raise self._error_http(e) from e
        except httpx.TransportError as e:
            raise ErrorModelo("No se pudo conectar con la API de Anthropic. Revisa la conexión.") from e
        try:
            datos = self._leer_stream(respuesta)
        finally:
            respuesta.close()
        if self._registro is not None:
            self._registro.registrar(self._ultima_pregunta(mensajes),
                                     datos["tokens_entrada"], datos["tokens_salida"])
        return datos

    # Comprueba la petición antes de enviarla: primer mensaje del usuario, roles, max_tokens y temperatura.
    def _validar(self, mensajes):
        if not mensajes:
            raise PeticionInvalida("No hay mensajes que enviar")
        if mensajes[0]["role"] != "user":
            raise PeticionInvalida("El primer mensaje debe ser de rol 'user'")
        for mensaje in mensajes:
            if mensaje["role"] not in ("user", "assistant"):
                raise PeticionInvalida(f"Rol no válido: {mensaje['role']!r}")
            if not isinstance(mensaje["content"], str):
                raise PeticionInvalida("El contenido de cada mensaje debe ser texto")
        if self._max_tokens <= 0:
            raise PeticionInvalida("max_tokens debe ser > 0")
        if self._temperatura is not None and not 0 <= self._temperatura <= 2:
            raise PeticionInvalida("temperature fuera de rango [0, 2]")

    # Abre la conexión en streaming. Si el servidor responde con error, lanza HTTPStatusError,
    # y tenacity reintenta solo los errores reintentables (429 y 5xx), hasta 5 intentos.
    @retry(
        retry=retry_if_exception(_es_reintentable),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def _abrir(self, payload):
        cabeceras = {
            "x-api-key": self._clave,
            "anthropic-version": self.VERSION_API,
            "content-type": "application/json",
        }
        peticion = self._http.build_request("POST", self.URL, json=payload, headers=cabeceras)
        respuesta = self._http.send(peticion, stream=True)
        if respuesta.status_code >= 400:
            try:
                detalle = respuesta.read().decode("utf-8", "replace")[:300]
            except Exception:  # sin cuerpo legible, basta con el código
                detalle = ""
            respuesta.close()
            raise httpx.HTTPStatusError(f"Error {respuesta.status_code}: {detalle}",
                                        request=peticion, response=respuesta)
        return respuesta

    # Lee los eventos del stream: el texto va llegando por fragmentos, y la herramienta pedida
    # llega como JSON troceado que se junta al final.
    def _leer_stream(self, respuesta):
        texto, herramienta, json_argumentos = "", None, ""
        tokens_entrada = tokens_salida = 0
        for linea in respuesta.iter_lines():
            if not linea.startswith("data:"):
                continue
            try:
                evento = json.loads(linea[len("data:"):].strip())
            except ValueError as e:
                raise ErrorModelo("La API devolvió un evento que no entiendo") from e
            tipo = evento.get("type")
            if tipo == "message_start":
                tokens_entrada = evento["message"].get("usage", {}).get("input_tokens", 0)
            elif tipo == "content_block_start":
                bloque = evento.get("content_block", {})
                if bloque.get("type") == "tool_use":
                    herramienta = bloque.get("name")
            elif tipo == "content_block_delta":
                delta = evento.get("delta", {})
                if delta.get("type") == "text_delta":
                    fragmento = delta.get("text", "")
                    texto += fragmento
                    if self._al_fragmento is not None:
                        self._al_fragmento(fragmento)
                elif delta.get("type") == "input_json_delta":
                    json_argumentos += delta.get("partial_json", "")
            elif tipo == "message_delta":
                tokens_salida = evento.get("usage", {}).get("output_tokens", tokens_salida)
            elif tipo == "error":
                raise ErrorModelo(f"Error de la API de Anthropic: {evento.get('error')}")
        argumentos = {}
        if json_argumentos:
            try:
                argumentos = json.loads(json_argumentos)
            except ValueError as e:
                raise ErrorModelo("La herramienta pedida llegó con argumentos que no entiendo") from e
        return {
            "texto": texto,
            "herramienta": herramienta,
            "argumentos": argumentos,
            "tokens_entrada": tokens_entrada,
            "tokens_salida": tokens_salida,
        }

    # Traduce un error HTTP a un mensaje que el usuario pueda entender.
    def _error_http(self, error):
        codigo = error.response.status_code
        if codigo in (401, 403):
            return ErrorModelo("La clave de Anthropic no es válida o no tiene permisos. Revisa LLM_API_KEY en .env")
        if codigo == 404:
            return ErrorModelo(f"Anthropic no encuentra el modelo «{self._modelo}»")
        if codigo == 429 or codigo >= 500:
            return ErrorModelo(f"Anthropic sigue respondiendo con error {codigo} tras reintentar. Prueba más tarde.")
        return ErrorModelo(f"Anthropic rechazó la petición ({error})")

    # Devuelve la pregunta del cliente del último turno, sin el resultado de herramientas que se
    # haya unido a ese mensaje, para anotarla en el registro.
    @staticmethod
    def _ultima_pregunta(mensajes):
        for mensaje in reversed(mensajes):
            if mensaje["role"] == "user":
                return mensaje["content"].split("\nResultado de la herramienta:")[0]
        return ""
