import json
import re
import unicodedata


# Pasa el texto a minúsculas y le quita las tildes.
def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


# Convierte un texto en número: int si es entero, float si no.
def _numero(texto):
    valor = float(texto.replace(",", "."))
    return int(valor) if valor.is_integer() else valor


class Respuesta:
    # Guarda una respuesta final (texto) o una petición de herramienta con sus argumentos.
    def __init__(self, texto=None, herramienta=None, argumentos=None):
        self.texto = texto
        self.herramienta = herramienta
        self.argumentos = argumentos or {}

    # True si el modelo pide una herramienta en lugar de responder.
    def es_llamada_herramienta(self) -> bool:
        return self.herramienta is not None


class Modelo:
    """Clase base de los modelos: deciden si responder o pedir una herramienta."""

    # Guarda el nombre del modelo.
    def __init__(self, nombre):
        self.nombre = nombre

    # Método abstracto: cada modelo decide si responder o pedir una herramienta.
    def responder(self, conversacion, herramientas) -> Respuesta:
        raise NotImplementedError("Cada modelo debe implementar responder()")


class ModeloEco(Modelo):
    # Crea el modelo con el nombre "eco".
    def __init__(self):
        super().__init__("eco")

    # Repite el último mensaje del usuario.
    def responder(self, conversacion, herramientas) -> Respuesta:
        ultimo = ""
        for mensaje in reversed(conversacion.get_mensajes()):
            if mensaje.rol == "usuario":
                ultimo = mensaje.contenido
                break
        return Respuesta(texto=f"Has dicho: {ultimo}")


class ModeloReglas(Modelo):
    PATRON_OPERACION = re.compile(r"(\d+[.,]?\d*)\s*([+\-*/x])\s*(\d+[.,]?\d*)")
    MONEDAS = {
        "usd": "USD", "dolar": "USD", "dolares": "USD",
        "gbp": "GBP", "libra": "GBP", "libras": "GBP",
        "jpy": "JPY", "yen": "JPY", "yenes": "JPY",
        "eur": "EUR", "euro": "EUR", "euros": "EUR",
    }
    MONEDAS_DISPARADORAS = {"USD", "GBP", "JPY"}
    PALABRAS_FAQ = ("envi", "devol", "horario", "pag")  # stems: also match "enviar", "devolución", "pagar"
    SALUDOS = {"hola", "buenas", "buenos", "hey", "saludos"}
    # Reto 4: "...y multiplícalo por 3", "...y réstale 5", "...divídelo entre 2"
    PATRON_ENCADENADA = re.compile(
        r"\b(multiplic|divid|sum|rest)\w*\s+(?:por|entre|a|le|en)?\s*(\d+(?:[.,]\d+)?)"
    )
    OPERADOR_ENCADENADO = {"multiplic": "*", "divid": "/", "sum": "+", "rest": "-"}
    PATRON_RESULTADO = re.compile(r"=\s*(-?\d+(?:\.\d+)?)")

    # Crea el modelo con el nombre "reglas".
    def __init__(self):
        super().__init__("reglas")

    # Pide una herramienta según el texto (operación, moneda o FAQ) o responde; tras un resultado, da la frase final.
    def responder(self, conversacion, herramientas) -> Respuesta:
        mensajes = conversacion.get_mensajes()
        if not mensajes:
            return Respuesta(texto="No estoy seguro, ¿puedes reformularlo?")
        ultimo = mensajes[-1]
        if ultimo.rol == "herramienta":
            pregunta, resultados = self._turno_actual(mensajes)
            siguiente = self._paso_encadenado(pregunta, resultados)
            if siguiente is not None:
                return siguiente
            return Respuesta(texto=self._frase_final(resultados))

        texto = ultimo.contenido
        normal = _normalizar(texto)
        palabras = re.findall(r"\w+", normal)

        m = self.PATRON_OPERACION.search(texto)
        if m:
            a, op, b = m.groups()
            op = "*" if op == "x" else op
            return Respuesta(
                herramienta="calculadora",
                argumentos={"a": _numero(a), "b": _numero(b), "operacion": op},
            )

        monedas = [self.MONEDAS[p] for p in palabras if p in self.MONEDAS]
        if self.MONEDAS_DISPARADORAS & set(monedas):
            origen = monedas[0]
            destino = next((x for x in monedas if x != origen), "EUR")
            cantidad = re.search(r"\d+(?:[.,]\d+)?", texto)
            return Respuesta(
                herramienta="conversor_moneda",
                argumentos={
                    "cantidad": _numero(cantidad.group()) if cantidad else None,
                    "origen": origen,
                    "destino": destino,
                },
            )

        if any(p in normal for p in self.PALABRAS_FAQ):
            return Respuesta(herramienta="buscador_faq", argumentos={"pregunta": texto})

        if self.SALUDOS & set(palabras):
            return Respuesta(texto="¡Hola! Soy NEXO, ¿en qué te ayudo?")

        return Respuesta(texto="No estoy seguro, ¿puedes reformularlo?")

    # Devuelve la última pregunta del usuario y los resultados de herramientas que vinieron después.
    @staticmethod
    def _turno_actual(mensajes):
        """Last user message and the tool results that came after it."""
        for i in range(len(mensajes) - 1, -1, -1):
            if mensajes[i].rol == "usuario":
                return mensajes[i].contenido, [m.contenido for m in mensajes[i + 1:] if m.rol == "herramienta"]
        return "", [m.contenido for m in mensajes if m.rol == "herramienta"]

    # Reto 4: si se pide una segunda operación, vuelve a pedir la calculadora con el resultado anterior.
    def _paso_encadenado(self, pregunta, resultados):
        """Reto 4: if the question asks for a second operation, chain it onto the first result."""
        if len(resultados) != 1 or resultados[0].startswith("Error"):
            return None
        operacion = self.PATRON_ENCADENADA.search(_normalizar(pregunta))
        valor = self.PATRON_RESULTADO.search(resultados[0])
        if not operacion or not valor:
            return None
        verbo, numero = operacion.groups()
        return Respuesta(
            herramienta="calculadora",
            argumentos={"a": _numero(valor.group(1)), "b": _numero(numero),
                        "operacion": self.OPERADOR_ENCADENADO[verbo]},
        )

    # Construye la respuesta final a partir de los resultados de las herramientas.
    @classmethod
    def _frase_final(cls, resultados):
        if len(resultados) >= 2 and not any(r.startswith("Error") for r in resultados):
            return f"Primero, {resultados[-2]}; después, {resultados[-1]}. ¿Necesitas algo más?"
        return cls._frase_resultado(resultados[-1])

    # Convierte un único resultado de herramienta en una frase para el usuario.
    @staticmethod
    def _frase_resultado(contenido):
        if contenido.startswith("Error"):
            return f"No he podido completar la operación. {contenido}"
        if contenido == "No encontrado":
            return "No he encontrado información sobre eso. ¿Puedes reformular la pregunta?"
        if re.fullmatch(r"[\d.\s+\-*/=]+", contenido):
            return f"El resultado es {contenido}. ¿Necesitas algo más?"
        if " = " in contenido:
            return f"{contenido}."
        return f"Según nuestra información: {contenido}"


class ModeloLLM(Modelo):
    """Modelo basado en un LLM local. El cliente (inyectado) hace la llamada de red;
    aquí solo se prepara el prompt y se interpreta la respuesta, en JSON."""

    # Argumentos que espera cada herramienta, para que el modelo los pida bien.
    PARAMETROS = {
        "calculadora": "a (número), b (número), operacion (+, -, *, /)",
        "conversor_moneda": "cantidad (número), origen (USD, EUR, GBP o JPY), destino (USD, EUR, GBP o JPY)",
        "buscador_faq": "pregunta (texto)",
    }
    # Roles de NEXO -> roles de la API. Los resultados de herramientas van como mensajes del usuario.
    ROL_API = {"usuario": "user", "asistente": "assistant"}

    # Recibe el cliente que habla con el servidor del modelo.
    def __init__(self, cliente, nombre="llm"):
        super().__init__(nombre)
        self._cliente = cliente

    # Manda la conversación al modelo y convierte su texto en una Respuesta.
    def responder(self, conversacion, herramientas) -> Respuesta:
        mensajes = [{"role": "system", "content": self._instrucciones(herramientas)}]
        mensajes += [self._a_api(m) for m in conversacion.get_mensajes()]
        return self._interpretar(self._cliente.completar(mensajes))

    # Prompt de sistema: el formato JSON que debe devolver y la lista de herramientas.
    def _instrucciones(self, herramientas):
        lineas = [
            "Eres NEXO, el asistente de atención al cliente de la tienda TechNova.",
            "Responde SIEMPRE con un único objeto JSON y nada más, en una de estas dos formas:",
            '{"respuesta": "texto para el usuario"}',
            '{"herramienta": "nombre", "argumentos": {...}}',
            "Usa una herramienta solo si hace falta. Si ya tienes el resultado de una herramienta, responde con \"respuesta\".",
            "Herramientas disponibles:",
        ]
        for h in herramientas:
            argumentos = self.PARAMETROS.get(h.nombre, "sin argumentos")
            lineas.append(f"- {h.nombre}: {h.descripcion}. Argumentos: {argumentos}")
        return "\n".join(lineas)

    # Traduce un mensaje de NEXO al formato de mensajes de la API.
    def _a_api(self, mensaje):
        if mensaje.rol == "herramienta":
            return {"role": "user", "content": f"Resultado de la herramienta: {mensaje.contenido}"}
        return {"role": self.ROL_API[mensaje.rol], "content": mensaje.contenido}

    # Si el JSON pide una herramienta, devuelve esa llamada; si no, devuelve el texto como respuesta.
    def _interpretar(self, texto):
        datos = self._extraer_json(texto)
        if isinstance(datos, dict):
            herramienta = datos.get("herramienta")
            argumentos = datos.get("argumentos") or {}
            if isinstance(herramienta, str) and herramienta and isinstance(argumentos, dict):
                return Respuesta(herramienta=herramienta, argumentos=argumentos)
            if isinstance(datos.get("respuesta"), str):
                texto = datos["respuesta"]
            else:
                texto = texto.strip()
        texto = texto.strip()
        if not texto:  # el modelo ha devuelto una respuesta vacía
            return Respuesta(texto="No he podido generar una respuesta. ¿Puedes reformularlo?")
        return Respuesta(texto=texto)

    # Busca el primer objeto JSON dentro del texto (el modelo a veces añade texto alrededor).
    @staticmethod
    def _extraer_json(texto):
        inicio, fin = texto.find("{"), texto.rfind("}")
        if inicio == -1 or fin <= inicio:
            return None
        try:
            return json.loads(texto[inicio:fin + 1])
        except json.JSONDecodeError:
            return None


class ModeloClaude(Modelo):
    """Modelo de Anthropic (Claude Haiku). Usa tool calling nativo: el modelo recibe el esquema
    de cada herramienta y pide la que necesita. El cliente (inyectado) hace la llamada de red."""

    SYSTEM = (
        "Eres NEXO, el asistente de atención al cliente de la tienda TechNova. "
        "Responde en español, de forma breve y amable. "
        "No uses Markdown: ni negritas, ni asteriscos, ni títulos; el texto se muestra en una consola de texto. "
        "Usa una herramienta solo si necesitas datos para responder. "
        "Si una herramienta devuelve un error, explícaselo al cliente y pide los datos que falten."
    )

    # Recibe el cliente que habla con la API de Anthropic.
    def __init__(self, cliente, nombre="claude"):
        super().__init__(nombre)
        self._cliente = cliente

    # Manda la conversación y las herramientas al modelo, y convierte su respuesta en una Respuesta.
    def responder(self, conversacion, herramientas) -> Respuesta:
        datos = self._cliente.completar(
            self._a_api(conversacion.get_mensajes()),
            herramientas=[h.esquema() for h in herramientas],
            system=self.SYSTEM,
        )
        if datos.get("herramienta"):
            return Respuesta(herramienta=datos["herramienta"], argumentos=datos.get("argumentos") or {})
        texto = (datos.get("texto") or "").strip()
        if not texto:
            return Respuesta(texto="No he podido generar una respuesta. ¿Puedes reformularlo?")
        return Respuesta(texto=texto)

    # Traduce los mensajes de NEXO al formato de la API. Une los mensajes seguidos del mismo rol
    # y quita los del principio que no sean del usuario, porque la API exige que empiece por el usuario.
    @staticmethod
    def _a_api(mensajes):
        api = []
        for mensaje in mensajes:
            if mensaje.rol == "herramienta":
                rol, contenido = "user", f"Resultado de la herramienta: {mensaje.contenido}"
            else:
                rol = "user" if mensaje.rol == "usuario" else "assistant"
                contenido = mensaje.contenido
            if api and api[-1]["role"] == rol:
                api[-1]["content"] += "\n" + contenido
            else:
                api.append({"role": rol, "content": contenido})
        while api and api[0]["role"] != "user":
            api.pop(0)
        return api
