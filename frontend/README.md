# Frontend · Recursos de estudio UTI

Interfaz del docente del Generador de Recursos. Está construida sobre la
[plantilla institucional UTI](https://github.com/andresinose/plantilla-UTI): React 18,
TypeScript, Vite y Tailwind 4, con sus componentes, colores y tema claro/oscuro.

Diseño aprobado: [menú, opción B](../docs/superpowers/specs/2026-10-28-frontend-menu-design.md).

## Qué hace hoy (P6a)

- **Ingreso** con código enviado al correo institucional (`@uti.edu.ec` o `@indoamerica.edu.ec`).
- **Inicio** con dos caminos:
  - **Generar herramientas**: subir el sílabo en PDF;
  - **Perfil docente**: visible, pero *en espera* hasta recibir la documentación.
- **Mis asignaturas**: las propias y las compartidas, con tu rol.
- **Mis recursos**: llega en la siguiente entrega (revisar y exportar herramientas).

## Arranque en desarrollo

Requiere Node.js ≥ 22.18, la base `genrecursos-db` levantada y la API del P4.

1. API (desde `backend/`), en modo desarrollo: el código de ingreso se imprime en su consola y no se envía ningún correo.

   ```powershell
   $env:ENTORNO = 'desarrollo'; $env:SMTP_MODO = 'consola'
   $env:API_ORIGEN = 'http://localhost:5173'; $env:AUTH_SECRETO = '<al menos 32 caracteres>'
   ..\.venv\Scripts\python.exe -m app.servidor --port 8001
   ```

2. Frontend (desde `frontend/`):

   ```bash
   npm install
   npm run dev
   ```

   Abre `http://localhost:5173`. Vite reenvía `/api/*` a `http://127.0.0.1:8001`, así el
   navegador ve un solo origen: la cookie de sesión (HttpOnly, Secure, SameSite=Lax) funciona
   en `localhost` sin HTTPS.

## Comprobaciones

```bash
npm run check          # tipos, pruebas unitarias (cliente de la API) y compilación
npm run test:browser   # 7 pruebas en navegador con la API simulada
```

En Windows, para usar el Chrome instalado: `$env:PLAYWRIGHT_CHANNEL = 'chrome'`.

## Reglas

- La sesión vive solo en la cookie HttpOnly; el frontend no guarda tokens ni correos.
- El sílabo se envía como cuerpo `application/pdf` (no multipart), de hasta 10 MB.
- Los errores de la API se muestran en español, sin detalles internos (`src/api/cliente.ts`).
