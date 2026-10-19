import math
import re
import unicodedata

from dominio.excepciones import ArgumentosInvalidos


# Convierte un argumento en número (acepta coma decimal) o lanza ArgumentosInvalidos.
def _como_numero(valor, nombre):
    if valor is None:
        raise ArgumentosInvalidos(f"Falta el argumento '{nombre}'")
    try:
        numero = float(str(valor).replace(",", "."))
    except ValueError as e:
        raise ArgumentosInvalidos(f"'{nombre}' no es un número: {valor!r}") from e
    if not math.isfinite(numero):
        raise ArgumentosInvalidos(f"'{nombre}' no es un número válido: {valor!r}")
    return numero


# Muestra el número sin decimales si es entero (4.0 -> "4").
def _formatear(numero):
    if numero == int(numero):
        return str(int(numero))
    return str(round(numero, 10))


# Pasa el texto a minúsculas y le quita las tildes.
def _normalizar(texto):
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


class Herramienta:
    """Clase base de todas las herramientas que puede usar el agente."""

    # Guarda el nombre y la descripción de la herramienta.
    def __init__(self, nombre, descripcion):
        self.nombre = nombre
        self.descripcion = descripcion

    # Método abstracto: cada herramienta hija lo implementa.
    def ejecutar(self, **kwargs) -> str:
        raise NotImplementedError("Cada herramienta debe implementar ejecutar()")

    # Texto con el que se muestra la herramienta en /herramientas.
    def __str__(self):
        return f"🔧 {self.nombre}: {self.descripcion}"


class Calculadora(Herramienta):
    OPERACIONES = ("+", "-", "*", "/")

    # Crea la calculadora con su nombre y descripción.
    def __init__(self):
        super().__init__("calculadora", "Operaciones aritméticas (+ - * /) entre dos números")

    # Hace la operación entre a y b y devuelve un texto como "2 + 3 = 5".
    def ejecutar(self, **kwargs) -> str:
        a = _como_numero(kwargs.get("a"), "a")
        b = _como_numero(kwargs.get("b"), "b")
        operacion = kwargs.get("operacion")
        if operacion not in self.OPERACIONES:
            raise ArgumentosInvalidos(
                f"Operación no válida: {operacion!r}. Usa una de: + - * /"
            )
        if operacion == "+":
            resultado = a + b
        elif operacion == "-":
            resultado = a - b
        elif operacion == "*":
            resultado = a * b
        else:
            if b == 0:
                raise ArgumentosInvalidos("No se puede dividir entre 0")
            resultado = a / b
        return f"{_formatear(a)} {operacion} {_formatear(b)} = {_formatear(resultado)}"


class ConversorMoneda(Herramienta):
    TASAS_A_EUR = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "JPY": 0.0062}

    # Crea el conversor con su nombre y descripción.
    def __init__(self):
        super().__init__("conversor_moneda", "Convierte cantidades entre EUR, USD, GBP y JPY")

    # Convierte la cantidad de la moneda de origen a la de destino, pasando por euros.
    def ejecutar(self, **kwargs) -> str:
        cantidad = _como_numero(kwargs.get("cantidad"), "cantidad")
        monedas = []
        for campo in ("origen", "destino"):
            valor = kwargs.get(campo)
            if valor is None:
                raise ArgumentosInvalidos(f"Falta el argumento '{campo}'")
            moneda = str(valor).upper()
            if moneda not in self.TASAS_A_EUR:
                raise ArgumentosInvalidos(
                    f"Moneda no soportada: {valor!r}. Disponibles: {', '.join(self.TASAS_A_EUR)}"
                )
            monedas.append(moneda)
        origen, destino = monedas
        resultado = cantidad * self.TASAS_A_EUR[origen] / self.TASAS_A_EUR[destino]
        return f"{_formatear(cantidad)} {origen} = {resultado:.2f} {destino}"


class BuscadorFAQ(Herramienta):
    FAQ = {
        "envio envios enviar plazo dias tarda tardan": "Los envíos tardan 24-48 h en península y 3-5 días en islas.",
        "devolucion devoluciones devolver garantia": "Tienes 30 días para devolver el producto sin dar explicaciones.",
        "horario horarios atencion abierto": "Atendemos de lunes a viernes de 9:00 a 18:00.",
        "pago pagos pagar tarjeta bizum paypal": "Aceptamos tarjeta, Bizum y PayPal.",
    }

    # Crea el buscador con su nombre y descripción.
    def __init__(self):
        super().__init__("buscador_faq", "Busca la respuesta en las preguntas frecuentes de TechNova")

    # Devuelve la respuesta de la FAQ que más palabras comparte con la pregunta.
    def ejecutar(self, **kwargs) -> str:
        pregunta = kwargs.get("pregunta")
        if not isinstance(pregunta, str) or not pregunta.strip():
            raise ArgumentosInvalidos("Falta el argumento 'pregunta'")
        palabras = set(re.findall(r"\w+", _normalizar(pregunta)))
        mejor, mejor_puntos = None, 0
        for claves, respuesta in self.FAQ.items():
            puntos = len(palabras & set(claves.split()))
            if puntos > mejor_puntos:
                mejor, mejor_puntos = respuesta, puntos
        return mejor if mejor is not None else "No encontrado"
