Conclusiones: ModeloReglas frente a Claude Haiku 5.5

Las 10 preguntas se hicieron con el script comparar_modelos.py, a los dos modelos, con las mismas herramientas. Los datos de coste y tokens salen de datos/uso_llm.csv, que también incluye las pruebas del chat, así que el total es de 19 llamadas.

1. Precisión

ModeloReglas acierta cuando la pregunta contiene una palabra clave o una operación con símbolo: envío, devolver, pago y "250 dólares" funcionan. Falla cuando la pregunta no encaja en sus patrones. Con "si compro 3 SSD a 79,90 euros, ¿cuánto pago?" responde con las formas de pago en lugar de calcular el total, y con "cuánto es 12 por 7" no entiende la operación escrita con palabras. En 4 de las 10 preguntas responde "No estoy seguro".

Claude Haiku responde bien a 8 de las 10 preguntas, incluidas las que ModeloReglas no entiende. Dos casos fallaron. En "¿a qué hora abrís?" el modelo pidió herramientas tres veces seguidas y el agente cortó con el error "no llegó a una respuesta final en 3 iteraciones". En "¿me recomiendas una gráfica para jugar?" respondió bien pidiendo más datos, pero añadió un párrafo sobre "la información que he recibido" que no venía de ninguna herramienta.

2. Velocidad

ModeloReglas responde en menos de 0,01 segundos porque no sale de la máquina. Claude tardó entre 0,9 y 4,2 segundos por pregunta, con una mediana de unos 2 segundos. El tiempo depende de la red y de cuántas herramientas pide el modelo: las preguntas que usan una herramienta tardan más porque hacen dos llamadas.

3. Consumo de tokens y coste

Cada llamada a Claude se registra en datos/uso_llm.csv con los tokens de salida y el coste en dólares. Las 19 llamadas del total anterior costaron 0,0031 dólares en conjunto, unas 0,0002 dólares por llamada, con precios de 0,10 dólares por millón de tokens de entrada y 0,50 por millón de salida. ModeloReglas no consume tokens ni cuesta nada.

4. Facilidad de uso

ModeloReglas funciona al instante: no necesita clave, ni internet, ni configuración. Claude necesita una clave de Anthropic en el archivo .env, conexión a internet y un saldo en la cuenta. A cambio, Claude entiende preguntas que no están escritas de una forma concreta y no hay que añadir patrones a mano. Para añadir Claude al proyecto solo fue necesario una clase nueva, ModeloClaude, y un comando en el chat. La clase Agente no cambió, que es lo que pedía la arquitectura por capas.

5. Robustez

ModeloReglas nunca falla por la red, pero tampoco responde lo que no tiene previsto. Claude depende de la red, de la clave y del servicio. Ante errores 429 y 5xx, el cliente reintenta hasta 5 veces con espera creciente, y los errores 400 se muestran sin reintentar. Un error de configuración, como una clave que falta o una temperatura no admitida por el modelo, se detecta con un mensaje claro antes o al enviar la petición. El punto débil que mostró la prueba es el límite de tres vueltas: cuando el modelo no llega a una respuesta, el chat muestra un error en lugar de una respuesta de cortesía, y eso se puede mejorar.
