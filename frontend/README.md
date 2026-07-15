# Interfaz React de RuralFindMe

Esta carpeta contiene la interfaz visual importada de Figma y adaptada para el contenedor de escritorio. No implementa búsquedas ni procesa archivos: todas las operaciones se delegan al objeto `backend` de Qt WebChannel definido en `src/bridge.ts`.

```powershell
npm ci
npm run typecheck
npm run build
```

La salida de producción se genera en `dist/` y PyInstaller la incluye dentro de la aplicación. Abrir `index.html` directamente en un navegador muestra un error de conexión deliberado porque Qt WebChannel solo existe dentro de RuralFindMe.
