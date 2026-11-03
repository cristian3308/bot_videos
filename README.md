# 🎬 Cybercrime Studio — Generador automático de videos (YouTube Shorts / TikTok)

Estudio profesional que convierte casos de ciberseguridad en videos verticales (1080×1920)
**de principio a fin, sin edición manual**: guion con IA, voz neuronal, visuales animados,
subtítulos karaoke, música, miniaturas y subida automática a tus cuentas. Incluye **panel web**,
**generación en lote**, **banco de temas** y **programador diario**. Funciona en **Windows y Linux**.

---

## ✨ Funciones principales

**Creación**
- Guion con IA: **OpenCode Go** (principal), Gemini, OpenAI, Ollama (local) o modo demo
- **Fallback inteligente de modelo**: si el modelo elegido falla, prueba otros automáticamente
- Voz neuronal gratis (Edge TTS): **45+ voces**, muestra en vivo, control de **velocidad y tono**
- **7 tipos de escena**: terminal, diagrama, evidencia, **mapa de ataque**, **stat (cifra gigante)**, **timeline**, intro/outro de marca
- **Subtítulos karaoke** (resaltado palabra por palabra) estilo TikTok
- **5 temas de color**, **zoom Ken-Burns**, **barra de progreso**, **transiciones fade**
- **Música**: 4 moods procedurales (dark/tense/action/suspense) o tu archivo propio **con ducking**
- **Logo** superpuesto + **miniatura de YouTube 1280×720** automática
- Editar el guion antes de renderizar y **previsualizar una escena**
- Series **"Parte 2"**: continúa un video anterior

**Automatización**
- **Generar en lote**: 1–20 videos seguidos desde noticias reales o tu banco de temas
- **Banco de temas** persistente
- **Programador diario**: produce videos solos a la hora que elijas

**Publicación**
- Subida automática a **YouTube** (API oficial) y **TikTok** (Content Posting API)
- Biblioteca con miniaturas, reproducción, descarga, Parte 2 y borrado

---

## 📁 Estructura

```
Creador_vidos/
├─ .env.example        # Plantilla de config (API keys)  ← COPIAR a .env
├─ requirements.txt
├─ Dockerfile          # Para correr 24/7 en un servidor
├─ run.py              # Lanza el PANEL WEB   (python run.py)
├─ cli.py              # Genera un video por consola
├─ config/settings.py  # Carga .env, rutas, detección de FFmpeg
├─ core/
│  ├─ news.py          # Noticias reales por RSS
│  ├─ llm.py           # Guion multi-proveedor + fallback de modelo
│  ├─ prompts.py       # Prompt maestro + caso demo
│  ├─ tts.py           # Voz neuronal (Edge TTS) + muestras
│  ├─ subtitles.py     # Subtítulos karaoke .ass
│  ├─ render.py        # Escenas HTML + Playwright + miniatura YT
│  ├─ assemble.py      # FFmpeg: audio (moods/ducking), subtítulos, logo
│  ├─ pipeline.py      # Orquestador (guion / render en 2 pasos)
│  ├─ batch.py         # Generación en lote
│  ├─ scheduler.py     # Programador diario
│  └─ store.py         # Banco de temas + config del programador (JSON)
├─ uploaders/          # youtube.py + tiktok.py (OAuth)
├─ web/                # Panel FastAPI (pestañas Crear / Automatizar / Biblioteca)
├─ data/               # topics.json, scheduler.json (se crean solos)
└─ credentials/        # Secretos OAuth (no se suben a git)
```

---

## 🚀 Instalación

### 1. Dependencias de Python
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. FFmpeg (no es de pip)
- **Windows:** `winget install Gyan.FFmpeg`  (reinicia la terminal)
- **Linux:**   `sudo apt update && sudo apt install -y ffmpeg`

### 3. Configuración / API keys
Copia la plantilla y rellena tus claves (**todas las API keys van en `.env`**):
- **Windows:** `copy .env.example .env`
- **Linux:**   `cp .env.example .env`

| Variable | Para qué | Dónde conseguirla |
|---|---|---|
| `OPENCODE_API_KEY` | Guion con OpenCode Go (principal) | https://opencode.ai → Console → API Keys |
| `OPENCODE_MODEL` | Modelo (ej. `glm-5.3`) | Botón "Modelos" del panel |
| `GEMINI_API_KEY` | Alternativa Gemini | https://aistudio.google.com/app/apikey |
| `OPENAI_API_KEY` | Alternativa OpenAI | https://platform.openai.com/api-keys |
| (Ollama) | Alternativa local gratis | https://ollama.com + `ollama pull llama3.1` |

> **Plan OpenCode Go:** usa los endpoints `/inference/go/...` (ya configurados en `.env.example`).
> Algunos modelos requieren activar **Global** en Privacy settings de tu workspace. Si uno falla,
> el bot prueba otro automáticamente.

---

## ▶️ Uso

### Panel web (recomendado)
```bash
python run.py
```
Abre **http://127.0.0.1:8000**. Tres pestañas:
- **⚙ Crear** — elige proveedor, modelo, voz (con muestra), tema, escenas, música, marca; genera el guion, edítalo, previsualiza una escena y renderiza.
- **🤖 Automatizar** — genera en lote, administra tu banco de temas y configura el programador diario.
- **🎞 Biblioteca** — tus videos con miniatura, reproducir, descargar, Parte 2, subir y borrar.

### Por consola
```bash
python cli.py --provider opencode --topic "El ataque a SolarWinds" --lang es
```

> Sin API keys, el bot funciona en **modo demo** (caso real pre-cargado).

---

## 🔑 Conectar tus cuentas

### YouTube
1. https://console.cloud.google.com/ → crea proyecto → habilita **YouTube Data API v3**.
2. Pantalla de consentimiento OAuth (Externo, añádete como tester).
3. Credenciales → **ID de cliente OAuth** → **App de escritorio** → descarga el JSON.
4. Guárdalo como `credentials/youtube_client_secret.json` y pulsa **Conectar YouTube**.

### TikTok
1. https://developers.tiktok.com/ → crea app → producto **Content Posting API**.
2. Copia `TIKTOK_CLIENT_KEY` y `TIKTOK_CLIENT_SECRET` en `.env` → pulsa **Conectar TikTok**.

> Hasta que TikTok apruebe tu app, los videos se suben como **borrador** y los publicas desde la app.

---

## 🐳 Correr 24/7 con Docker

```bash
docker build -t cybercrime-studio .
docker run -d -p 8000:8000 --env-file .env -v "$PWD/output_videos:/app/output_videos" cybercrime-studio
```
Abre `http://localhost:8000`. Con el **programador** activado, produce videos solo cada día.

---

## 🧩 Notas técnicas
- Música ambiental sintetizada por FFmpeg (sin copyright). Con archivo propio se aplica **ducking**.
- Videos de solo animaciones de código (sin rostros): no requieren la etiqueta de "contenido sintético".
- Playwright usa Chromium headless; `run.py` configura el event loop correcto en Windows.

## ⚖️ Uso responsable
Contenido **educativo/documental** sobre casos reales. Las "terminales" y "payloads" son
recreaciones visuales, no instrucciones operativas para atacar sistemas.
