import json
import os
import urllib.error
import urllib.request

from dominio.excepciones import ErrorModelo


class ClienteLLM:
    """Habla con un servidor local compatible con la API de OpenAI (Ollama, LM Studio o serverMLX).

    Usa solo la biblioteca estándar: no hace falta clave ni instalar nada más.
    La URL y el modelo se pueden fijar con las variables NEXO_LLM_URL y NEXO_LLM_MODELO.
    """

    # Ollama expone la API en el puerto 11434. LM Studio usa http://localhost:1234/v1.
    URL_POR_DEFECTO = "http://localhost:11434/v1"
    MODELO_POR_DEFECTO = "qwen2.5:7b"

    # Guarda el modelo, la URL del servidor, el tiempo máximo de espera y la temperatura.
    # Si no se pasan, usa las variables de entorno y, si no existen, los valores por defecto.
    def __init__(self, modelo=None, url_base=None, timeout=120, temperatura=0.2):
        self._modelo = modelo or os.environ.get("NEXO_LLM_MODELO") or self.MODELO_POR_DEFECTO
        url = url_base or os.environ.get("NEXO_LLM_URL") or self.URL_POR_DEFECTO
        self._url = url.rstrip("/") + "/chat/completions"
        self._timeout = timeout
        self._temperatura = temperatura

    # Envía los mensajes al servidor y devuelve el texto de la respuesta.
    def completar(self, mensajes) -> str:
        cuerpo = json.dumps({
            "model": self._modelo,
            "messages": mensajes,
            "temperature": self._temperatura,
            "stream": False,
        }).encode("utf-8")
        peticion = urllib.request.Request(
            self._url, data=cuerpo, method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(peticion, timeout=self._timeout) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ErrorModelo(f"El servidor del modelo respondió con error {e.code}. "
                              f"¿Está descargado el modelo «{self._modelo}»?") from e
        except OSError as e:  # servidor apagado, sin red o tiempo de espera agotado
            raise ErrorModelo(f"No puedo conectar con el modelo local en {self._url}. "
                              "¿Está encendido Ollama o LM Studio?") from e
        except ValueError as e:  # la respuesta no es JSON
            raise ErrorModelo("El modelo local devolvió una respuesta que no entiendo") from e
        try:
            return datos["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ErrorModelo("El modelo local devolvió una respuesta que no entiendo") from e
