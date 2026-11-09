# Frontend · Menú principal (P6, primera entrega) — Diseño

**Fecha:** 2026-10-28 · **Aprobado por el usuario:** opción B de las maquetas (`.superpowers/brainstorm/…/menu-b-v2.html`).

## Intención

El docente entra al aplicativo y debe ver de inmediato los dos caminos de la colmena:

1. **Generar herramientas:** sube su documentación (hoy, el sílabo en PDF) y la colmena prepara las herramientas de aprendizaje.
2. **Perfil docente:** la planificación del docente y su parametrización. **Se muestra pero queda «en espera»** hasta que llegue la documentación institucional.

El usuario pidió empezar ya el desarrollo del menú sobre la plantilla institucional [plantilla-UTI](https://github.com/andresinose/plantilla-UTI).

## Decidido por el usuario

- Layout **B**: barra superior y, en el inicio, dos tarjetas grandes lado a lado («Generar herramientas» destacada y «Perfil docente» desactivada con la insignia «en espera»).
- Base visual: la plantilla UTI (colores, componentes y tema claro/oscuro).

## Decidido por Claude (revisable)

- **Ubicación:** `frontend/` en este repositorio. Es una copia de la plantilla sin `.git`, `node_modules` ni `dist`, como indica su README. La galería de ejemplos se elimina.
- **Pestañas de la barra:** Inicio, Mis asignaturas y Mis recursos. A la derecha: correo, tema y «Salir».
- **Alcance de esta entrega:** el menú funciona contra la API real del P4.
  - ingreso con código por correo;
  - inicio con los dos caminos;
  - subida del sílabo (`POST /silabos`) con el resumen que devuelve la colmena;
  - lista de «Mis asignaturas».
  - «Mis recursos» y la generación por clase o momento quedan como siguiente entrega del P6, con un aviso en pantalla.
- **Conexión con la API en desarrollo:** el servidor de Vite (`http://localhost:5173`) reenvía `/api/*` a `http://127.0.0.1:8001/*`, así el navegador ve un solo origen. La API se configura con `API_ORIGEN=http://localhost:5173`, `ENTORNO=desarrollo` y `SMTP_MODO=consola`. En producción (P7) el proxy será el servidor web.
- **Sin router:** la plantilla no trae uno. La navegación es un estado de la aplicación (`vista`), como hace la Navbar de la plantilla. Si más adelante se necesitan URLs profundas, se agrega un router.
- **Sin librerías nuevas:** solo las de la plantilla (React, lucide-react y Tailwind).

## Metas y no-metas

- **Meta:** que un docente ingrese, vea el menú, suba su sílabo y vea sus asignaturas, con los colores y la accesibilidad de la plantilla.
- **No-metas en esta entrega:** generar y revisar herramientas desde la pantalla, exportar a HTML/PDF/DOCX, el chat de ajustes (P5) y el perfil docente real.
- **Anti-metas:**
  - mostrar el perfil docente como si funcionara;
  - guardar el token o los datos personales en `localStorage`; la sesión vive solo en la cookie HttpOnly;
  - inventar contenido en el frontend.

## Restricciones

- Las escrituras deben llevar el `Origin` exacto; `fetch` con `credentials: "include"`.
- `POST /silabos` recibe el PDF en el cuerpo con `Content-Type: application/pdf`, de hasta 10 MB.
- Mensajes de error en español, sin mostrar detalles internos.
- Accesibilidad de la plantilla: foco visible, `aria-*`, tema claro y oscuro, y diseño que funcione en el móvil.
