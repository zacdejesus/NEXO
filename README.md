# NEXO · asistente de TechNova (Nivel 3: agente pro)

Agente de IA "de juguete" en Python con arquitectura por capas. El programa solo usa la biblioteca estándar; `pytest` hace falta solo para las pruebas.

## Ejecución

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # pytest
python main.py                    # desde la raíz del proyecto
pytest                            # pruebas (65)
```

## Estructura

| Capa | Archivos |
|---|---|
| Presentación | `presentacion/chat_consola.py` |
| Servicios | `servicios/agente.py` |
| Dominio | `dominio/excepciones.py`, `mensaje.py`, `herramientas.py`, `modelos.py` |
| Persistencia | `persistencia/repositorio_conversaciones.py`, `registro_uso.py` |
| Conexión | `main.py` (único sitio donde se unen las piezas) |

No hay `print()` ni `input()` en `dominio/` ni `servicios/` (lo verifica una prueba).

## Comandos del chat

| Comando | Acción |
|---|---|
| texto normal | Se envía a NEXO |
| `/herramientas` | Lista las herramientas |
| `/modelo eco` · `/modelo reglas` | Cambia de modelo en caliente |
| `/historial` | Mensajes, roles y tokens estimados |
| `/guardar` | Guarda la conversación actual e informa de su id |
| `/cargar <id>` | Restaura una conversación completa en el agente |
| `/lista` | Conversaciones guardadas |
| `/nueva` | Nueva conversación (con id nuevo; las guardadas no se tocan) |
| `/stats` | Resumen del registro de uso |
| `/salir` | Termina |

Los errores (`ErrorAgente` y derivadas, o cualquier fallo inesperado) se muestran como mensaje y el chat sigue abierto.

## Persistencia JSON

`RepositorioConversaciones(carpeta="datos/conversaciones")` guarda cada conversación en `<id>.json`
(`to_dict()`, UTF-8, escritura atómica) y la reconstruye con `Conversacion.from_dict()` / `Mensaje.from_dict()`,
conservando id, fechas, roles, contenidos y orden. Los ids solo admiten `A-Z a-z 0-9 _ -`, así que no se puede
salir de la carpeta (`../x`). Id inexistente, JSON corrupto o contenido inválido lanzan `ErrorPersistencia`
(subclase de `ErrorAgente`).

## Registro CSV

`RegistroUso("datos/uso.csv")` añade una fila por ejecución de herramienta, éxito o fallo:
`fecha,herramienta,argumentos,exito,milisegundos` (cabecera una sola vez, duración medida con `perf_counter`).
`resumen()` devuelve `{"total", "usos", "fallos"}` (a cero si no hay registros). El agente funciona igual con `registro_uso=None`.

## Retos del Nivel 3

### Reto 4: varias herramientas en una pregunta
«convierte 100 USD a euros y multiplícalo por 3» → `conversor_moneda` → `calculadora` → respuesta:
`Primero, 100 USD = 92.00 EUR; después, 92 * 3 = 276.`

**El agente no se ha modificado.** Su bucle ya permite hasta 3 vueltas. Es `ModeloReglas` quien, al ver el
primer resultado, detecta una segunda operación en la pregunta («multiplícalo por», «divídelo entre»,
«súmale», «réstale») y pide otra herramienta con el número del resultado anterior. Si el primer paso falla,
no encadena.

### Reto 5: tests con `pytest`
La carpeta `tests/` replica la estructura del proyecto:

```
tests/
├── dominio/        test_excepciones · test_mensaje · test_herramientas · test_modelos
├── servicios/      test_agente
├── persistencia/   test_repositorio_conversaciones · test_registro_uso
├── presentacion/   test_chat_consola
├── test_main.py          ← main.py (ciclo real guardar → cerrar → reabrir → cargar)
├── test_arquitectura.py  ← reglas globales: sin print/input en dominio/servicios, sin isinstance en el agente
└── ayudantes.py          ← crear_agente(), ejecutar_chat()
```

El dominio se puede probar sin entrada ni salida porque no tiene `input()` ni `print()`. El chat se prueba
inyectando `entrada`/`salida` en `ChatConsola`.

### Reto 6: resumen automático
Cuando `Conversacion.agregar()` detecta que se superaría el **80 %** del límite de tokens, sustituye los
mensajes antiguos por un único mensaje-resumen (`[Resumen de N mensajes anteriores] Temas: …`) y conserva
intactos los más recientes (hasta 4, o menos si hace falta para bajar del 80 %).
- El resumen recoge las preguntas del usuario y arrastra los temas de resúmenes anteriores, sin anidarlos.
- Ocupa como máximo el 25 % del límite: los temas más antiguos se van descartando.
- Si ni resumiendo cabe el mensaje (por ejemplo, uno enorme), se lanza `LimiteContextoSuperado` y la
  conversación no cambia.
- El chat avisa con `🗜 He resumido los mensajes antiguos…`.
- Se puede desactivar con `Conversacion(resumen_automatico=False)`.

## Diagrama de clases

Solo aparecen los métodos públicos principales. Los detalles están en el código de cada clase.

![Diagrama de clases de NEXO](docs/diagrama_clases.png)

<details>
<summary>Código Mermaid (GitHub lo dibuja; también se puede pegar en mermaid.live)</summary>

```mermaid
classDiagram
    direction TB

    class ChatConsola {
        +iniciar()
    }
    class Agente {
        +procesar(texto_usuario) str
        +cambiar_modelo(modelo)
        +nueva_conversacion()
    }
    class Conversacion {
        +id : str
        +agregar(mensaje)
        +get_mensajes() list
        +tokens_estimados() int
    }
    class Mensaje {
        +rol : str
        +contenido : str
        +fecha : str
    }
    class Modelo {
        <<abstract>>
        +nombre : str
        +responder(conversacion, herramientas) Respuesta
    }
    class ModeloEco
    class ModeloReglas
    class Respuesta {
        +texto : str
        +herramienta : str
        +argumentos : dict
    }
    class Herramienta {
        <<abstract>>
        +nombre : str
        +descripcion : str
        +ejecutar(**kwargs) str
    }
    class Calculadora
    class ConversorMoneda
    class BuscadorFAQ
    class RepositorioConversaciones {
        +guardar(conversacion)
        +cargar(id_conv) Conversacion
        +listar() list
    }
    class RegistroUso {
        +registrar(herramienta, argumentos, exito, milisegundos)
        +resumen() dict
    }
    class ErrorAgente {
        <<exception>>
    }
    class HerramientaNoEncontrada
    class ArgumentosInvalidos
    class LimiteContextoSuperado
    class ErrorPersistencia

    ChatConsola --> Agente
    ChatConsola --> RepositorioConversaciones
    ChatConsola ..> ErrorAgente : captura

    Agente *-- Conversacion
    Conversacion *-- Mensaje
    Agente --> Modelo
    Agente o-- Herramienta
    Agente --> RegistroUso

    Modelo <|-- ModeloEco
    Modelo <|-- ModeloReglas
    Modelo ..> Respuesta : devuelve

    Herramienta <|-- Calculadora
    Herramienta <|-- ConversorMoneda
    Herramienta <|-- BuscadorFAQ

    RepositorioConversaciones ..> Conversacion : guarda / carga

    ErrorAgente <|-- HerramientaNoEncontrada
    ErrorAgente <|-- ArgumentosInvalidos
    ErrorAgente <|-- LimiteContextoSuperado
    ErrorAgente <|-- ErrorPersistencia
```

</details>

**Cómo leerlo:**
- **Herencia** (`<|--`): los 3 tipos de herramienta, los 2 modelos y las 4 excepciones heredan de su clase base. El agente usa herramientas y modelos a través de la base, sin saber cuál es cuál (polimorfismo).
- **Composición** (`*--`): el `Agente` crea **su** `Conversacion`, y la `Conversacion` está formada por `Mensaje`s.
- **Agregación** (`o--`): el `Agente` usa herramientas que se crean **fuera**, en `main.py`.
- **Asociación** (`-->`): una clase guarda una referencia a otra.
- **Dependencia** (`..>`): una clase devuelve, guarda o captura algo de otra.
- Las capas solo dependen hacia abajo: Presentación → Servicios → Dominio, y Persistencia → Dominio. `main.py` las conecta todas.

## Nivel alcanzado y uso de la IA

- Nivel alcanzado: 3, con los retos 4 (varias herramientas), 5 (pytest) y 6 (resumen automático).
- Uso de la IA: este código fue generado con un asistente de IA a partir del enunciado.
  **Pendiente de completar por la pareja:** qué se pidió a la IA, qué se cambió y las respuestas a las
  preguntas de reflexión (deben ir con vuestras palabras, según la sección 11 del enunciado).
