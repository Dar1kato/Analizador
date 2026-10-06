"""
Backend FastAPI que recibe código Python (en JSON), lo envía a la API de OpenAI
y devuelve un archivo .txt con el mismo código comentado, explicando la
complejidad temporal (Big-O, Big-Theta y Big-Omega) de cada parte.

Ejecución:
    uv run --env-file .env fastapi dev main.py
Pruebas:
    http://127.0.0.1:8000/docs

Variables de entorno (archivo .env en la raíz del proyecto):
    OPENAI_API_KEY=sk-...        (obligatoria)
    OPENAI_MODEL=gpt-5.5         (opcional, valor por defecto: gpt-5.5)
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.5")
TEMPERATURE = 0.2  # Casi determinista, con algo de flexibilidad al redactar

if not OPENAI_API_KEY:
    raise RuntimeError(
        "Falta la variable de entorno OPENAI_API_KEY. "
        "Agrégala al archivo .env y ejecuta con: "
        "uv run --env-file .env fastapi dev main.py"
    )

client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=120.0)

SYSTEM_PROMPT = """\
Eres un experto en análisis de algoritmos y complejidad computacional.

Recibirás código Python. Tu tarea es devolver EXACTAMENTE ese mismo código, sin
modificar, agregar ni eliminar ninguna línea de código, pero con comentarios en
ESPAÑOL que expliquen la complejidad temporal de cada parte relevante
(declaraciones, ciclos, condicionales, llamadas a funciones, recursión, etc.),
indicando cuál es su complejidad y por qué.

Reglas:
1. Usa comentarios con "#" encima o al lado de la línea o bloque que explican.
2. Define explícitamente qué representa "n" (o las variables de tamaño de
   entrada) en el primer comentario del análisis.
3. Al final del código agrega un comentario en bloque (cadena multilínea
   delimitada por triples comillas dobles) que contenga:
   - Complejidad temporal Big-O (peor caso)
   - Complejidad temporal Big-Theta (caso promedio / cota ajustada)
   - Complejidad temporal Big-Omega (mejor caso)
   - Una explicación detallada del razonamiento detrás de cada una de las
     tres. Si Theta no existe como cota única (porque Big-O y Big-Omega
     difieren), indícalo y explica por qué.
4. Responde ÚNICAMENTE con el código comentado. No incluyas fences de markdown
   (```), saludos, introducciones ni texto fuera del código.
"""

# --------------------------------------------------------------------------- #
# Modelos de datos
# --------------------------------------------------------------------------- #
class CodeRequest(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        description="Código Python a analizar (como string; los saltos de línea se escriben \\n).",
        examples=[
            "def buscar(lista, objetivo):\n"
            "    for i in range(len(lista)):\n"
            "        if lista[i] == objetivo:\n"
            "            return i\n"
            "    return -1\n"
        ],
    )


# --------------------------------------------------------------------------- #
# Manejo de errores de OpenAI
# --------------------------------------------------------------------------- #
def manejar_error_openai(error: Exception) -> HTTPException:
    """Traduce una excepción de la API de OpenAI a un HTTPException de FastAPI."""
    if isinstance(error, AuthenticationError):
        return HTTPException(401, "API key de OpenAI inválida o sin permisos.")
    if isinstance(error, RateLimitError):
        return HTTPException(429, "Límite de uso o cuota de OpenAI excedido. Intenta más tarde.")
    if isinstance(error, BadRequestError):
        return HTTPException(400, f"Petición inválida para OpenAI: {error.message}")
    # APITimeoutError hereda de APIConnectionError, por eso se revisa primero.
    if isinstance(error, APITimeoutError):
        return HTTPException(504, "OpenAI tardó demasiado en responder (timeout).")
    if isinstance(error, APIConnectionError):
        return HTTPException(503, "No se pudo conectar con la API de OpenAI.")
    if isinstance(error, APIStatusError):
        return HTTPException(502, f"Error de la API de OpenAI (código {error.status_code}).")
    return HTTPException(500, f"Error inesperado al consultar OpenAI: {error}")


# --------------------------------------------------------------------------- #
# Llamada al modelo
# --------------------------------------------------------------------------- #
async def analizar_codigo(code: str) -> str:
    """Envía el código a OpenAI y devuelve el código comentado."""
    kwargs = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": code},
        ],
    }
    try:
        response = await client.chat.completions.create(**kwargs, temperature=TEMPERATURE)
    except BadRequestError as e:
        # Algunos modelos (p. ej. los de razonamiento) no aceptan "temperature":
        # en ese caso se reintenta sin ese parámetro.
        if "temperature" in str(e).lower():
            response = await client.chat.completions.create(**kwargs)
        else:
            raise

    content = response.choices[0].message.content
    if not content:
        raise HTTPException(502, "OpenAI devolvió una respuesta vacía.")
    return content


# --------------------------------------------------------------------------- #
# Aplicación FastAPI
# --------------------------------------------------------------------------- #
app = FastAPI(
    title="Analizador de complejidad temporal",
    description="Recibe código Python y devuelve un .txt con el código comentado y su análisis Big-O, Big-Theta y Big-Omega.",
)


@app.post("/analyze", response_class=PlainTextResponse)
async def analyze(request: CodeRequest) -> PlainTextResponse:
    try:
        resultado = await analizar_codigo(request.code)
    except HTTPException:
        raise
    except OpenAIError as e:
        raise manejar_error_openai(e)

    return PlainTextResponse(
        content=resultado,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="analisis_complejidad.txt"'},
    )
