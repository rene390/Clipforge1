# ClipForge AI — paquete con frontend y backend conectables

## Por qué el botón no procesaba
Netlify publicó la interfaz estática, pero no ejecuta FastAPI, FFmpeg ni Whisper. Este paquete configura la web para hablar con un backend independiente y habilita CORS para el dominio Netlify de la captura.

## 1. Desplegar backend en Render
1. Sube esta carpeta a un repositorio privado de GitHub.
2. En Render elige **New → Blueprint** y conecta el repositorio (detectará `render.yaml` y el Dockerfile).
3. Espera a que el servicio `clipforge-ai-api` termine de desplegar. Copia su URL pública, por ejemplo `https://clipforge-ai-api.onrender.com`.
4. El procesamiento de video y Whisper consume memoria/CPU. Si el plan gratuito no tiene recursos suficientes o duerme el servicio, usa un plan con recursos adecuados. El primer uso descarga el modelo y tarda más.

## 2. Conectar la web Netlify existente
1. Abre `static/config.js`.
2. Cambia `https://TU-SERVICIO.onrender.com` por la URL real del backend.
3. Vuelve a desplegar el contenido de esta carpeta en Netlify (o actualiza el repositorio conectado a Netlify).
4. Recarga la web. Pega un enlace autorizado, marca la confirmación y pulsa el botón.

El backend permite por defecto el dominio Netlify mostrado en la captura: `https://iridescent-zuccutto-70dd74.netlify.app`. Si el nombre de tu sitio cambia, actualiza `FRONTEND_ORIGIN` en Render con el nuevo dominio.

## Uso responsable
Solo procesa videos tuyos o para los que tengas permiso expreso. Respeta los derechos de autor, los términos de YouTube y las restricciones técnicas. La detección de momentos es una heurística de densidad de diálogo; no promete viralidad. Los clips se guardan en el disco local del servicio: para producción añade almacenamiento persistente, limpieza automática, límites de duración/tamaño y una cola de trabajos.
