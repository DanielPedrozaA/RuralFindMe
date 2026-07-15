# Especificación del parser basada en los PDF reales

Fecha de inspección: 15 de julio de 2026. Los tres archivos suministrados son exportaciones de Microsoft Excel 2016 en PDF 1.5. Tienen texto seleccionable, líneas de tabla y una imagen de la identidad visual «Salud». No requieren OCR.

## Ronda detectada

- Profesión: `MEDICINA`.
- Fecha de generación y fecha indicada en el título de la ronda: `16/04/2026`.
- Los tres títulos dicen «sorte de plazas», tal como aparece en el documento; el parser tolera ese texto sin corregir la fuente.
- Los PDF no publican un identificador de ronda distinto de la fecha. En esta versión, `allocation_round` se deriva de la fecha detectada.
- La identidad institucional aparece como imagen con la palabra «Salud». El texto extraíble no contiene un nombre más específico; la aplicación no lo inventa.

## 1. Plazas_Asignadas_MEDICINA.pdf

Propósito: relacionar plazas asignadas con el tipo y número de identificación del profesional.

- 17 páginas.
- 434 filas de datos.
- Tabla normal de 9 columnas repetida en cada página.
- Estado implícito por pertenecer al reporte: `Plaza asignada`.

Columnas reales, en orden de la publicación:

1. `Código Plaza`
2. `Tipo identificación profesional asignado`
3. `Número de identificación profesional asignado`
4. `Nombre Departamento`
5. `Nombre Municipio`
6. `Profesión`
7. `Código de Habilitación (REPS)`
8. `Número Sede (REPS)`
9. `Nombre de la IPS - Sede`

No contiene nombre del profesional, modalidad, fecha de inicio, duración, contacto ni observaciones. La aplicación muestra esos campos como no publicados y no intenta inferirlos.

## 2. Plazas_Vacantes_MEDICINA.pdf

Propósito: relacionar plazas que quedaron vacantes. No es una lista de profesionales.

- 8 páginas.
- 195 filas de datos.
- Tabla normal de 7 columnas repetida en cada página.
- No tiene tipo ni número de identificación.

Columnas reales:

1. `Código Plaza`
2. `Profesión`
3. `Nombre Departamento`
4. `Nombre Municipio`
5. `Código de Habilitación (REPS)`
6. `Número Sede (REPS)`
7. `Nombre de la IPS - Sede`

Estas filas se contabilizan y validan como parte de la ronda, pero nunca se usan como coincidencias de una persona.

## 3. Profesionales_Sin_Plaza_MEDICINA.pdf

Propósito: relacionar profesionales sin plaza asignada.

- 1 página.
- 0 filas de datos en el archivo suministrado; la tabla tiene filas vacías.
- 2 columnas: `Tipo identificación` y `Número de identificación`.
- Si una publicación futura trae una fila sin otro estado explícito, el estado derivado del título es `Profesional sin plaza asignada` y se clasifica como `NOT_SELECTED`.

El documento no contiene las palabras «exonerado», «exonerada», «no seleccionado» ni otra categoría individual. La aplicación no transforma la ausencia de una persona en exoneración.

## Reglas de reconstrucción

1. PyMuPDF detecta las líneas y celdas de cada tabla.
2. Los encabezados se resuelven mediante alias configurables y no por posición fija.
3. Se eliminan encabezados repetidos y filas de título/fecha.
4. Una fila asignada o vacante debe tener un código completo con patrón `dígitos-dígitos`.
5. Una fila de profesional sin plaza debe tener un número normalizado completo de 5 a 15 dígitos.
6. Los saltos de línea dentro de una celda se unen con espacios. Las continuaciones físicas sin clave se conservan en el texto de evidencia de la fila anterior.
7. Cada registro conserva archivo, página, texto reconstruido, campos y confianza.
8. Los números se comparan por igualdad después de quitar separadores. Nunca se usa una búsqueda parcial.

## Clasificación determinista

- Coincidencia única en asignadas: `ASSIGNED`.
- Coincidencia única en profesionales sin plaza: `NOT_SELECTED`, salvo que la fila publique explícitamente una exoneración, en cuyo caso es `EXEMPT`.
- Ninguna coincidencia de número ni nombre: `NOT_FOUND`, sin afirmar exoneración.
- Estados incompatibles, asignaciones múltiples, discrepancia entre tipo/nombre y número, o confianza menor de 60 %: `AMBIGUOUS`.

Los estados configurables existen para publicaciones futuras, pero no alteran la semántica observada en estos tres archivos.

## OCR

Si no hay texto seleccionable y sí hay imágenes, el validador exige Tesseract disponible localmente. El OCR solo crea evidencia conservadora cuando encuentra un tipo de identificación seguido de un token numérico completo; esa evidencia recibe 45 % de confianza y por tanto se revela como `AMBIGUOUS` hasta verificación manual.
