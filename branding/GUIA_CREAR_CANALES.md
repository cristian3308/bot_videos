# 🚀 Guía para crear los canales — DÍA CERO

Paso a paso para abrir **YouTube** y **TikTok** con la marca de esta carpeta.
Todo lo visual (logo, banner, nombre, bios) ya está en `branding/`.

---

## ✅ Checklist rápido (lo que ya tienes)
- [x] Nombre: **DÍA CERO**
- [x] Handle: **@diacero** (y alternativas en `MARCA_DEL_CANAL.md`)
- [x] Foto de perfil: `logo_perfil_1024.png`
- [x] Banner de YouTube: `banner_youtube_2560x1440.png`
- [x] Bios y descripciones listas para copiar (abajo)
- [x] Hashtags fijos

---

## 📺 1) Crear el canal de YouTube

1. Entra a **youtube.com** con tu cuenta de Google (o crea una nueva solo para el canal).
2. Arriba a la derecha → foto → **Crear un canal**.
3. **Nombre del canal:** `Día Cero`
4. **Handle:** `@diacero` (si está ocupado, prueba los de `MARCA_DEL_CANAL.md`).
5. Ve a **Personalizar canal → Diseño / Imagen de marca**:
   - **Foto de perfil** → sube `logo_perfil_1024.png`
   - **Banner (imagen de encabezado)** → sube `banner_youtube_2560x1440.png`
   - **Marca de agua de video** → opcional, puedes usar `logo_perfil_1024.png`
6. Pestaña **Información básica**:
   - **Descripción** → copia el bloque "YouTube" de `MARCA_DEL_CANAL.md`
   - **Enlaces / contacto** → opcional
7. Sube tu primer Short (vertical 1080×1920 → ya es el formato que genera el panel).

> **Tamaños YouTube:** perfil ≥ 98×98 (tu PNG de 1024 sobra) · banner 2560×1440 (zona segura 1546×423, ya respetada).

---

## 🎵 2) Crear la cuenta de TikTok

1. Descarga **TikTok** o entra a **tiktok.com** → **Regístrate** (usa email o el mismo Google).
2. **Editar perfil:**
   - **Nombre:** `Día Cero`
   - **Usuario:** `diacero` (mismo que YouTube si se puede)
   - **Foto de perfil** → sube `logo_perfil_1024.png` (TikTok la recorta en círculo; tu logo está centrado, se ve bien)
   - **Bio** → copia el bloque "TikTok" de `MARCA_DEL_CANAL.md`
3. (Recomendado) Activa **Cuenta de empresa / creador** en Ajustes → te da estadísticas y más opciones de audio.
4. Sube el mismo video vertical. En la descripción pon 4-6 hashtags fijos.

> **Tamaños TikTok:** perfil 200×200 mínimo (tu PNG de 1024 sobra) · video 1080×1920.

---

## 🔗 3) Conectar la subida automática (opcional, desde el panel)

El panel ya tiene botones **Conectar YouTube** / **Conectar TikTok**. Para que funcionen necesitas claves de desarrollador:

- **YouTube Data API v3** → consola de Google Cloud → crea proyecto → habilita la API → credenciales OAuth → descarga el JSON en `credentials/` y ponlo en `.env` (`YOUTUBE_CLIENT_SECRET=...`).
- **TikTok Content Posting API** → developers.tiktok.com → crea app → pide permiso de publicación → claves en `.env`.

Mientras no las tengas, generas el video en el panel, pulsas **⬇ Video** y lo subes a mano. El resto (guion, voz, miniatura) ya es automático.

---

## 📈 4) Primeros pasos recomendados
1. Sube **3-5 videos de golpe** antes de difundir (que el canal no se vea vacío). Usa **Automatizar → Generar en lote**.
2. Encadena **series "Parte 1, 2, 3"** de un mismo caso grande (Stuxnet, SolarWinds, Mirai…) para enganchar.
3. Publica constante: 2-4/semana. Usa el **Programador** del panel.
4. El mismo video sirve para **YouTube Shorts + TikTok + Reels** (todos son 9:16).

---

*Toda la identidad (nombre, colores, bios) está en `branding/MARCA_DEL_CANAL.md`.
Para regenerar el logo/banner con otro nombre: `python -c "from core.branding import generate_brand_pack; generate_brand_pack('NOMBRE','tagline','branding')"`.*
