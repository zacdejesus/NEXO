import re
import unicodedata


def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def _numero(texto):
    texto = texto.replace(",", ".")
    return int(texto) if texto.isdigit() else float(texto)


class Respuesta:
    def __init__(self, texto=None, herramienta=None, argumentos=None):
        self.texto = texto
        self.herramienta = herramienta
        self.argumentos = argumentos or {}

    def es_llamada_herramienta(self) -> bool:
        return self.herramienta is not None


class Modelo:
    """Clase base de los modelos: deciden si responder o pedir una herramienta."""

    def __init__(self, nombre):
        self.nombre = nombre

    def responder(self, conversacion, herramientas) -> Respuesta:
        raise NotImplementedError("Cada modelo debe implementar responder()")


class ModeloEco(Modelo):
    def __init__(self):
        super().__init__("eco")

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

    def __init__(self):
        super().__init__("reglas")

    def responder(self, conversacion, herramientas) -> Respuesta:
        mensajes = conversacion.get_mensajes()
        if not mensajes:
            return Respuesta(texto="No estoy seguro, ¿puedes reformularlo?")
        ultimo = mensajes[-1]
        if ultimo.rol == "herramienta":
            return Respuesta(texto=self._frase_resultado(ultimo.contenido))

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
