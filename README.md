# RuralFindMe — ¿Dónde me tocó?

Aplicación de escritorio local para consultar tres PDF de resultados colombianos de Servicio Social Obligatorio en medicina. La interfaz visual está hecha con React/Vite y se ejecuta dentro de una ventana PySide6; Python valida los documentos, reconstruye sus tablas y determina el resultado. No se inicia un servidor web, no se llama a APIs y no se envían documentos ni identificaciones fuera del equipo.

## Funciones principales

- Selección conjunta, en un único diálogo de escritorio Qt aislado del proceso WebEngine, de exactamente tres PDF: plazas asignadas, plazas vacantes y profesionales sin plaza. Un fallo del selector no puede cerrar la aplicación principal.
- Metadatos seguros en la interfaz: nombre del archivo, tamaño, páginas, categoría, ronda, recuento y validación. Las rutas locales no se exponen a JavaScript.
- Validación en segundo plano de duplicados, corrupción, contraseña, PDF sin texto y compatibilidad de ronda.
- Extracción en segundo plano para mantener activa la ventana.
- Reconstrucción de tablas por encabezados configurables y comparación exacta de identificaciones normalizadas.
- Resultados diferenciados: `ASSIGNED`, `EXEMPT`, `NOT_SELECTED`, `NOT_FOUND`, `AMBIGUOUS` y `ERROR`.
- Etapas de procesamiento emitidas por Python; los tiempos de la interfaz solo animan etapas que ya ocurrieron.
- Copia y exportación `.txt` con la identificación enmascarada.
- Limpieza del estado sensible al restablecer o cerrar. Sin almacenamiento permanente de los PDF ni de la identificación consultada.
- Bloqueo explícito de solicitudes de red desde el motor web embebido.
- Renderizado acelerado por GPU para una interfaz fluida, con un modo de software opcional para controladores GPU/ANGLE incompatibles.

El análisis de los documentos suministrados está en [docs/PARSER_SPEC.md](docs/PARSER_SPEC.md): 434 plazas asignadas, 195 vacantes y 0 filas de profesionales sin plaza para la ronda del 16/04/2026.

## Arquitectura

```text
React/Vite (frontend/dist)
          │ cola local de comandos y eventos JSON
          ▼
  sondeo controlado por PySide6
          │
          ▼
PySide6 + Python
  ├─ selectores y exportación nativos
  ├─ validación y parser de PDF
  ├─ búsqueda y clasificación determinista
  └─ QWebEngineView sin acceso de red
```

Qt WebChannel solo identifica el contenedor local de confianza; ninguna acción de usuario lo invoca directamente. Python es la única fuente de verdad: React no abre archivos, no interpreta PDF y no calcula resultados. El contrato entre ambos lados está documentado en [docs/WEBCHANNEL.md](docs/WEBCHANNEL.md).

## Ejecutar desde código

Requiere Python 3.12 o posterior y Node.js con npm.

```powershell
cd frontend
npm ci
npm run build
cd ..
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

En macOS/Linux, activa el entorno con `source .venv/bin/activate`.

Para modificar la interfaz durante el desarrollo:

```powershell
cd frontend
npm run typecheck
npm run build
```

La aplicación siempre carga `frontend/dist/index.html` como archivo local. `npm run dev` sirve para trabajar visualmente en React, pero no reemplaza el contenedor PySide6 ni ofrece el puente Python.

Si un controlador gráfico incompatible provoca una ventana vacía o un cierre de WebEngine, inicie una sesión en modo seguro por software:

```powershell
$env:RURALFINDME_SOFTWARE_RENDERING = "1"
python -m app.main
```

Elimine la variable con `Remove-Item Env:RURALFINDME_SOFTWARE_RENDERING` para volver a la aceleración normal.

## Pruebas

```powershell
python -m pytest
cd frontend
npm run typecheck
npm run build
npm audit
```

Los datos automatizados son ficticios. Los PDF oficiales usados para comprobar el parser no se copian al repositorio.
El archivo [`fixtures/anonymized_records.json`](fixtures/anonymized_records.json) contiene los valores ficticios canónicos para pruebas manuales, demostraciones y nuevas pruebas automatizadas; no representa personas ni instituciones reales.

Para demostrar el resultado `NOT_SELECTED` de la ronda del 16/04/2026, use [`fixtures/demo_profesionales_sin_plaza_16-04-2026.pdf`](fixtures/demo_profesionales_sin_plaza_16-04-2026.pdf) como reemplazo ficticio del reporte vacío e ingrese `999999999999999`. El archivo se puede regenerar con `python scripts/create_demo_without_position_pdf.py` y está rotulado explícitamente como documento no oficial.

Las pautas de seguridad, pruebas y limpieza para contribuir están en [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Crear el ejecutable de Windows

Desde PowerShell:

```powershell
.\scripts\build_windows.ps1
.\scripts\make_portable.ps1
```

El resultado es una distribución `onedir` en `dist\RuralFindMe\RuralFindMe.exe` y un ZIP portable en `dist\RuralFindMe-1.1.3-Windows-portable.zip`. Se debe compartir la carpeta completa o el ZIP, no el ejecutable aislado. Python y Node.js no son necesarios en el equipo final.

## Empaquetar en macOS

PyInstaller no compila de forma cruzada; este paso debe ejecutarse en un Mac:

```bash
chmod +x scripts/build_macos.sh
./scripts/build_macos.sh
```

El resultado queda en `dist/RuralFindMe.app`. Para distribución pública se debe firmar con Developer ID y notarizar con las herramientas de Apple.

Para aplicar una firma ad-hoc y crear el ZIP portable para compartir de forma privada:

```bash
chmod +x scripts/make_portable_macos.sh
./scripts/make_portable_macos.sh
```

El resultado queda en `dist/RuralFindMe-<versión>-macOS.zip`. Otros usuarios pueden necesitar abrir la aplicación con clic derecho → **Abrir** porque una firma ad-hoc no sustituye la firma Developer ID ni la notarización de Apple.

## OCR opcional

Los tres PDF inspeccionados contienen texto seleccionable. Para documentos escaneados, instala Tesseract OCR y el idioma español (`spa`) y deja `tesseract` disponible en `PATH`. Todo el OCR se ejecuta localmente. Sin Tesseract, un PDF compuesto solo por imágenes se rechaza con un mensaje claro.

## Soportar rondas futuras

1. Añade títulos o alias de columnas en `app/config/parser_config.json`.
2. Añade vocabulario oficial en `app/config/status_keywords.json`, manteniendo separados los estados publicados.
3. Agrega una prueba anonimizada que reproduzca la nueva estructura.
4. Cambia `table_parser.py` solo si la publicación deja de usar tablas por filas; conserva siempre archivo, página y evidencia original enmascarada.

Consulta [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) para los límites semánticos y de publicación.
