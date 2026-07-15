# Contrato del puente de escritorio

React se ejecuta dentro de Qt WebEngine y comprueba la presencia del transporte local de Qt WebChannel. Las operaciones no invocan métodos WebChannel directamente: React encola comandos y el contenedor PySide6 los recoge cada 250 ms; los eventos de Python vuelven por la misma consulta controlada por el host. Los objetos complejos viajan como JSON UTF-8. Python conserva los archivos, el análisis y el resultado como única fuente de verdad.

Este intercambio fuera de los manejadores de clic y teclado evita una recursión COM de Windows observada al invocar Qt WebChannel desde eventos de entrada. La selección de PDF se ejecuta además en un proceso auxiliar; las rutas pasan por un archivo temporal eliminado inmediatamente y nunca llegan a React.

## Comandos de React hacia Python

| Comando | Argumentos | Efecto |
|---|---|---|
| `selectPdfs` | — | Abre el selector aislado para elegir exactamente tres PDF juntos. |
| `validateDocuments` | `allowMismatch: boolean` | Valida el conjunto y, si se autoriza, acepta una diferencia de ronda advertida. |
| `searchDoctor` | `idType`, `idNumber`, `fullName` | Ejecuta el análisis y la búsqueda en segundo plano. |
| `resetApplication` | — | Borra documentos, análisis y resultado de memoria. |
| `exportResult` | — | Abre el diálogo nativo para guardar un resumen enmascarado. |
| `copyResult` | — | Copia al portapapeles un resumen enmascarado. |
| `updatePreferences` | `soundEnabled`, `reducedAnimation` | Actualiza preferencias de la sesión. |
| `notifyReveal` | — | Reproduce localmente el sonido de revelación si está habilitado. |

## Eventos de Python hacia React

| Evento | Carga | Uso |
|---|---|---|
| `stateSnapshot` | JSON | Documentos, ronda, posibilidad de continuar y preferencias. |
| `documentSelected` | `slot`, JSON o `null` | Actualiza una tarjeta después de seleccionar o retirar un PDF. |
| `documentBatchStateChanged` | `busy`, `message` | Informa el inicio y el final de la validación conjunta sin bloquear la ventana. |
| `documentValidationUpdated` | JSON | Resultado de validar el conjunto de tres documentos. |
| `processingStageChanged` | `stage`, `message` | Etapa real del trabajo de Python. |
| `searchCompleted` | JSON | Resultado final y evidencia segura. |
| `processingFailed` | texto | Error validado o excepción de procesamiento. |
| `exportCompleted` | texto | Confirmación de exportación o copia. |

Las etapas posibles son, en orden:

1. `VALIDATING_DOCUMENTS`
2. `EXTRACTING_TEXT`
3. `IDENTIFYING_DOCUMENT_TYPES`
4. `SEARCHING_IDENTIFICATION`
5. `VERIFYING_EVIDENCE`
6. `CLASSIFYING_RESULT`
7. `READY_TO_REVEAL`

Los tipos finales son `ASSIGNED`, `EXEMPT`, `NOT_SELECTED`, `NOT_FOUND`, `AMBIGUOUS` y `ERROR`.

## Frontera de privacidad

- Los payloads de documento nunca contienen la ruta local.
- La identificación consultada y la de cada registro se transmiten enmascaradas.
- El texto de evidencia se sanea para sustituir cualquier aparición exacta de la identificación.
- React no recibe objetos Python, manejadores de archivos ni acceso al sistema de archivos.
- La página solo puede navegar a recursos `file`, `qrc`, `data` y `blob`; las solicitudes de red se cancelan en Python y también se restringen con CSP.
