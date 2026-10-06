# Analizador de complejidad temporal

Backend hecho con **FastAPI** y **uv** que recibe código Python, lo envía a la API de **OpenAI** y devuelve un archivo `.txt` con el mismo código comentado, explicando la complejidad temporal de cada parte y, al final, un comentario en bloque con las complejidades **Big-O**, **Big-Theta** y **Big-Omega** y su razonamiento.

Todo el backend vive en un solo archivo: `main.py`.

---

## Tabla de contenidos

1. [Cómo funciona](#cómo-funciona)
2. [Endpoints](#endpoints)
3. [Configuración](#configuración)
4. [Manejo de errores](#manejo-de-errores)
5. [Replicar el proyecto](#replicar-el-proyecto)
6. [Generar el requirements.txt](#generar-el-requirementstxt)
7. [Estructura del proyecto](#estructura-del-proyecto)
8. [Notas y limitaciones](#notas-y-limitaciones)

---

## Cómo funciona

El flujo de una petición es el siguiente:

```
Cliente (Swagger / curl)
        │  POST /analyze  {"code": "..."}
        ▼
   FastAPI valida el JSON (Pydantic)
        │
        ▼
   analizar_codigo()  ──►  API de OpenAI (Chat Completions)
        │                    · mensaje de sistema: instrucciones de análisis
        │                    · mensaje de usuario: el código recibido
        ▼
   Código comentado (texto)
        │
        ▼
   Respuesta text/plain descargable: analisis_complejidad.txt
```

Piezas principales de `main.py`:

| Componente | Función |
|---|---|
| `CodeRequest` | Modelo Pydantic que valida que el cuerpo sea un JSON con el campo `code` (string no vacío). |
| `SYSTEM_PROMPT` | Instrucciones para la IA: devolver el mismo código sin modificarlo, con comentarios en español sobre la complejidad de cada parte, definir qué es `n` y cerrar con un comentario en bloque con Big-O, Big-Theta y Big-Omega y su explicación. |
| `analizar_codigo()` | Llama a OpenAI con `temperature=0.2`. Si el modelo rechaza ese parámetro (algunos modelos no lo aceptan), reintenta automáticamente sin él. Si la respuesta llega vacía, devuelve un 502. |
| `manejar_error_openai()` | Traduce las excepciones de la API de OpenAI a respuestas HTTP con un mensaje claro. |
| `analyze()` | Endpoint `POST /analyze`; une todo lo anterior y devuelve el `.txt`. |

Detalles de comportamiento:

- **Cliente asíncrono:** se usa `AsyncOpenAI`, de modo que el servidor no se bloquea mientras espera a OpenAI.
- **Timeout:** 120 segundos por petición a OpenAI.
- **Sin validación del código:** el backend asume que el código recibido es Python válido y no verifica que la IA lo deje intacto.
- **Arranque seguro:** si falta `OPENAI_API_KEY`, la aplicación no arranca y muestra un mensaje explicativo.

---

## Endpoints

### `POST /analyze`

Analiza el código recibido y devuelve el resultado como archivo de texto.

**Request**

- Content-Type: `application/json`
- Cuerpo:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `code` | string | Sí (mínimo 1 carácter) | Código Python a analizar. Los saltos de línea se escriben como `\n` y las comillas dobles como `\"`. |

Ejemplo de cuerpo:

```json
{
  "code": "def raizCuadrada(n):\n    if n < 0:\n        return None\n    x = n\n    y = (x + 1) // 2\n    while y < x:\n        x = y\n        y = (x + n // x) // 2\n    return x\n"
}
```

**Response exitosa (200)**

- Content-Type: `text/plain; charset=utf-8`
- Header: `Content-Disposition: attachment; filename="analisis_complejidad.txt"`
- Cuerpo: el código recibido con comentarios en español y, al final, un comentario en bloque con Big-O, Big-Theta, Big-Omega y el razonamiento.

Ilustración del formato (el contenido real lo genera la IA y puede variar):

```python
# n = longitud de la lista
def buscar(lista, objetivo):
    # El ciclo recorre la lista completa en el peor caso: O(n)
    for i in range(len(lista)):
        if lista[i] == objetivo:   # Comparación: O(1)
            return i               # Retorno temprano: O(1)
    return -1

"""
Big-O (peor caso): O(n)
Big-Theta: no existe una cota ajustada única (el mejor y el peor caso difieren)
Big-Omega (mejor caso): Ω(1)

Razonamiento: ...
"""
```

**Errores**

| Código | Causa |
|---|---|
| 400 | Petición inválida para OpenAI. |
| 401 | API key de OpenAI inválida o sin permisos. |
| 422 | El cuerpo no cumple el esquema (falta `code` o está vacío). Lo genera FastAPI. |
| 429 | Límite de velocidad o cuota de OpenAI excedido. |
| 500 | Error inesperado. |
| 502 | OpenAI devolvió un error o una respuesta vacía. |
| 503 | No se pudo conectar con OpenAI. |
| 504 | OpenAI tardó demasiado en responder (timeout). |

Los errores se devuelven como JSON: `{"detail": "mensaje"}`.

Ejemplo con `curl`:

```bash
curl -X POST 'http://127.0.0.1:8000/analyze' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{"code": "def f(n):\n    return n * 2\n"}' \
  -o analisis_complejidad.txt
```

### Endpoints generados por FastAPI

| Ruta | Descripción |
|---|---|
| `GET /docs` | Interfaz Swagger UI para probar los endpoints desde el navegador. |
| `GET /redoc` | Documentación alternativa (ReDoc). |
| `GET /openapi.json` | Esquema OpenAPI de la API. |

### Probar desde Swagger

1. Abre `http://127.0.0.1:8000/docs`.
2. Expande `POST /analyze` y pulsa **Try it out**.
3. Pega tu JSON en el cuerpo (el campo trae un ejemplo precargado) y pulsa **Execute**.
4. Descarga el resultado con el enlace **Download file**.

---

## Configuración

La configuración se hace con variables de entorno, definidas en un archivo `.env` en la raíz del proyecto (junto a `main.py`):

```env
OPENAI_API_KEY=sk-tu-clave
OPENAI_MODEL=gpt-5.5
```

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `OPENAI_API_KEY` | Sí | — | API key de OpenAI. La cuenta debe tener saldo disponible en la API (se factura aparte de ChatGPT). |
| `OPENAI_MODEL` | No | `gpt-5.5` | Modelo a utilizar. Consulta los modelos disponibles en <https://platform.openai.com/docs/models>. |

> **Importante:** no subas el archivo `.env` al repositorio. Agrégalo al `.gitignore`.

Si cambias el `.env` con el servidor en marcha, **reinícialo**: el auto-reload de `fastapi dev` detecta cambios en el código, pero no vuelve a leer las variables de entorno.

---

## Manejo de errores

La función `manejar_error_openai()` convierte las excepciones del SDK de OpenAI en respuestas HTTP:

| Excepción de OpenAI | Código HTTP |
|---|---|
| `AuthenticationError` | 401 |
| `RateLimitError` | 429 |
| `BadRequestError` | 400 |
| `APITimeoutError` | 504 |
| `APIConnectionError` | 503 |
| `APIStatusError` (otros) | 502 |
| Cualquier otra | 500 |

Un **429** puede significar dos cosas: que la cuenta no tiene saldo (`insufficient_quota`) o que se enviaron demasiadas peticiones en poco tiempo. Revisa el saldo en `platform.openai.com` → Settings → Billing.

---

## Replicar el proyecto

### Requisitos

- Python 3.10 o superior
- [uv](https://docs.astral.sh/uv/) instalado
- Una API key de OpenAI con saldo disponible

### 1. Obtener el proyecto

```bash
git clone <URL-del-repositorio>
cd <carpeta-del-proyecto>
```

### 2. Instalar las dependencias

**Opción A: con uv (recomendada)**

Usa el `pyproject.toml` (y el `uv.lock`, si existe) del proyecto:

```bash
uv sync
```

**Opción B: con `requirements.txt`**

```bash
uv venv
uv pip install -r requirements.txt
```

o, sin uv:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Si empiezas el proyecto desde cero:**

```bash
uv init
uv add "fastapi[standard]" openai
```

### 3. Configurar las variables de entorno

Crea el archivo `.env` en la raíz del proyecto:

```env
OPENAI_API_KEY=sk-tu-clave
OPENAI_MODEL=gpt-5.5
```

### 4. Ejecutar el backend con `run.sh`

Dale permisos de ejecución (solo la primera vez) y ejecútalo:

```bash
chmod +x run.sh
./run.sh
```

El script levanta el servidor de FastAPI. Una vez en marcha, abre <http://127.0.0.1:8000/docs> para probar el endpoint.

> Si prefieres arrancar sin el script, el comando equivalente es:
> `uv run --env-file .env fastapi dev main.py`

---

## Generar el requirements.txt

Con uv, desde la raíz del proyecto:

```bash
uv export --no-hashes --no-emit-project -o requirements.txt
```

- `--no-hashes` produce un archivo más legible (sin hashes de verificación).
- `--no-emit-project` evita que el propio proyecto aparezca como dependencia.

Alternativa, a partir del `pyproject.toml`:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Vuelve a generarlo cada vez que agregues o quites dependencias.

---

## Estructura del proyecto

```
.
├── main.py            # Backend completo (FastAPI + llamada a OpenAI)
├── run.sh             # Script para levantar el servidor
├── .env               # Variables de entorno (NO subir al repositorio)
├── pyproject.toml     # Dependencias y metadatos (uv)
├── uv.lock            # Versiones bloqueadas (uv)
├── requirements.txt   # Dependencias en formato pip (opcional)
└── README.md
```

---

## Notas y limitaciones

- El resultado lo genera un modelo de IA: puede equivocarse, sobre todo en Big-Theta y Big-Omega (casos con recursión, salidas tempranas o estructuras de datos). Conviene revisar el razonamiento antes de darlo por correcto.
- El backend no valida que el código sea Python correcto ni comprueba que la IA lo haya dejado sin modificar.
- Aunque el prompt le pide a la IA que no use fences de markdown (```` ``` ````), el modelo podría incluirlos; el backend no los elimina.
- Cada petición consume saldo de la API de OpenAI; el costo depende del modelo elegido y del tamaño del código.
