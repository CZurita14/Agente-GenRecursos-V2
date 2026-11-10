// Pruebas reales en navegador del menú (P6a). La API se simula con page.route: sin backend.
import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

let browser;
let server;
const origin = 'http://127.0.0.1:4187';
let serverOutput = '';
before(async () => {
  server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4187', '--strictPort'], { stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', chunk => { serverOutput += chunk; });
  server.stderr.on('data', chunk => { serverOutput += chunk; });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error(serverOutput);
    try { ready = (await fetch(origin)).ok; } catch { /* Esperando Vite. */ }
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(ready, serverOutput || 'Vite no inició.');
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
});
after(async () => { await browser?.close(); server?.kill(); });

const USUARIO = { correo: 'docente@uti.edu.ec', rol: 'docente' };
const MATERIA = (id, estado, extra = {}) => ({ id_sga: id, codigo_pf: 'B26-SOFT-3', paralelo: '1', nombre: 'ANALISIS DE DATOS',
  carrera: 'SOFTWARE', estado_sga: 'ACTIVA', estado, asignatura_id: estado === 'importada' || estado === 'sin_cambios' ? 'a1' : null, ...extra });
const MATERIAS = [MATERIA('m1', 'importada'), MATERIA('m2', 'no_disponible', { paralelo: '2', nombre: 'ESTADISTICA' }),
  MATERIA('m3', 'invalida', { codigo_pf: 'B26-SOFT-4', nombre: 'PROBABILIDAD' })];

const MENU_ASIG = [{ numero: 2, inicio: '2026-10-12', fin: '2026-10-18', cierra_momentos: [2], clases: [
  { clase_id: 'M2-S1', numero_clase: 1, dia: 'mie', fecha: '2026-10-14', momento: 2, momento_titulo: 'Planeación',
    contenidos: ['DISTRIBUCIONES'], ra: ['RA2'], entregables: [] }] },
{ numero: 3, inicio: '2026-10-19', fin: '2026-10-25', cierra_momentos: [3], clases: [
  { clase_id: 'M3-S1', numero_clase: 2, dia: 'mie', fecha: '2026-10-21', momento: 3, momento_titulo: 'Resolución',
    contenidos: ['ESTIMACIÓN'], ra: ['RA3'], entregables: [] }] }];
const RECURSO = validado => ({ id: 'r1', trabajo_id: 't1', ambito_id: 'M2-S1', herramienta: 'cuestionario', version_silabo: '1.0',
  estado: 'requiere_revision', revision: 0, creado: '2026-10-28T10:00:00Z', silabo_actualizado: false, evidencia_vigente: true,
  validado: !!validado, validado_por: validado ? USUARIO.correo : null, validado_en: validado ? '2026-10-28T11:00:00Z' : null,
  evidencia: { borrador: true, verificaciones: { i1: [] }, veredictos: { i1: 'el revisor considera correctas las opciones 1 y 3' } },
  contenido: [{ item_id: 'i1', pregunta: '¿Qué prueba corresponde?', contexto: 'Una empresa ficticia.', correcta: 0,
    opciones: [{ texto: 'Prueba t' }, { texto: 'ANOVA' }, { texto: 'Chi cuadrado' }, { texto: 'Regresión' }] }], presentacion: [] });
// Ficha: contenido con claves internas; la vista solo usa la presentación ordenada (y sus rutas para editar).
const FICHA = { ...RECURSO(false), id: 'r2', herramienta: 'ficha_clase', evidencia: {}, verificacion_edicion: null,
  contenido: { aplicacion: { clase_id: 'M2-S1', ejemplo: { enunciado: 'Una tienda mide ventas.', pasos: ['Calcular la media', 'Interpretar'] } },
    conceptual: { numero_clase: 1, ideas_clave: ['Idea A', 'Idea B'] } },
  presentacion: [
    { tipo: 'lista', titulo: 'Ideas clave', items: ['Idea A', 'Idea B'], numerada: false, ruta: ['conceptual', 'ideas_clave'] },
    { tipo: 'grupo', titulo: 'Ejemplo resuelto', bloques: [
      { tipo: 'texto', titulo: 'Enunciado', texto: 'Una tienda mide ventas.', ruta: ['aplicacion', 'ejemplo', 'enunciado'] },
      { tipo: 'lista', titulo: 'Pasos', items: ['Calcular la media', 'Interpretar'], numerada: true, ruta: ['aplicacion', 'ejemplo', 'pasos'] }] },
    { tipo: 'tabla', titulo: 'Cómo se valora', columnas: ['Indicador', 'Qué observar'], filas: [['Precisión', 'Cálculo correcto']], rutas: [[null, null]] }] };
const HOJA = { ...RECURSO(false), id: 'r3', ambito_id: 'asignatura', herramienta: 'hoja_ruta', evidencia: {}, contenido: {},
  presentacion: [{ tipo: 'texto', titulo: 'Producto final', texto: 'Informe', ruta: null }] };
/** Respuesta simulada del PUT: el contenido recibido, revisión + 1 y alertas de la edición. */
const EDITADO = (base, cuerpo) => ({ ...base, contenido: cuerpo.contenido, revision: cuerpo.revision + 1, evidencia_vigente: false,
  validado: false, validado_por: null, verificacion_edicion: {} });

/** API simulada: `sesion` dice si /auth/yo responde 200 o 401. */
async function abrir({ sesion = true, viewport, rutas = {} } = {}) {
  const context = await browser.newContext(viewport ? { viewport } : {});
  const page = await context.newPage();
  const estado = { sesion, llamadas: [] };
  // Solo rutas que empiezan por /api/: «**/api/**» también capturaría el módulo /src/api/cliente.ts.
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    estado.llamadas.push({ ruta, metodo: route.request().method(), tipo: route.request().headers()['content-type'], cuerpo: route.request().postData() });
    if (rutas[ruta]) return rutas[ruta](route, estado);
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (ruta === '/asignaturas/a1/chat') return json(200, { pedidos: [], siguiente: null });
    if (ruta === '/auth/yo') return estado.sesion ? json(200, USUARIO) : json(401, { detail: 'Sesión requerida' });
    if (ruta === '/auth/ingresar') { estado.sesion = true; return json(200, { correo: USUARIO.correo, materias: MATERIAS }); }
    if (ruta === '/materias') return json(200, MATERIAS);
    if (ruta === '/auth/salir') { estado.sesion = false; return json(200, { mensaje: 'Sesión cerrada' }); }
    if (ruta === '/asignaturas') return json(200, [{ id: 'a1', nombre: 'ANALISIS DE DATOS', codigo_pf: 'B26-SOFT-3', version_silabo: '1.0', agente: 'ingenierias', rol: 'dueno', dueno: USUARIO.correo }]);
    // --- P6b: menú, catálogo, generación, avance, recurso, validación ---
    if (ruta === '/asignaturas/a1/menu') return json(200, { id: 'a1', rol: 'dueno', version_silabo: '1.0', menu: MENU_ASIG });
    if (ruta === '/asignaturas/a1/herramientas') {
      const restringido = url.searchParams.get('id')?.startsWith('M3');
      return json(200, { ambito: url.searchParams.get('ambito'), restringido, perfil_sugerido: 'fundamentacion',
        motivo: restringido ? 'La política de IA de este momento excluye la IA en una evaluación.' : null,
        politica_ia: 'Se permite IA como asistente.',
        herramientas: restringido ? []
          : [{ id: 'cuestionario', recomendada: true }, { id: 'ficha_clase', recomendada: false }] });
    }
    if (ruta === '/asignaturas/a1/generar') return json(202, { trabajos: [{ id: 't1', herramienta: 'cuestionario', estado: 'en_cola' }] });
    if (ruta === '/asignaturas/a1/trabajos') {
      estado.consultas = (estado.consultas ?? 0) + 1;
      return json(200, [{ id: 't1', herramienta: 'cuestionario', ambito_tipo: 'clase', ambito_id: 'M2-S1', lotes_total: 1,
        lotes_hechos: 1, error: null, estado: 'requiere_revision', recurso_id: 'r1' }]);
    }
    if (ruta === '/asignaturas/a1/recursos') return json(200, [{ id: 'r1', trabajo_id: 't1', ambito_id: 'M2-S1',
      herramienta: 'cuestionario', version_silabo: '1.0', estado: 'requiere_revision', revision: 0, creado: '2026-10-28T10:00:00Z' },
      { id: 'r2', trabajo_id: 't2', ambito_id: 'M2-S1', herramienta: 'ficha_clase', version_silabo: '1.0', estado: 'listo',
        revision: 0, creado: '2026-10-28T10:05:00Z' },
      { id: 'r3', trabajo_id: 't3', ambito_id: 'asignatura', herramienta: 'hoja_ruta', version_silabo: '1.0', estado: 'listo',
        revision: 0, creado: '2026-10-28T10:06:00Z', validado: true }]);
    // --- P6c: edición (PUT con revisión y contenido completo) ---
    if (route.request().method() === 'PUT') {
      const cuerpo = JSON.parse(route.request().postData());
      (estado.puts ??= []).push({ ruta, cuerpo });
      if (estado.falla422) return json(422, { detail: 'El contenido editado no es válido' });
      return json(200, EDITADO(ruta.endsWith('/r2') ? FICHA : RECURSO(false), cuerpo));
    }
    if (ruta === '/asignaturas/a1/recursos/r2') return json(200, FICHA);
    if (ruta === '/asignaturas/a1/recursos/r3') return json(200, HOJA);
    if (ruta === '/asignaturas/a1/recursos/r1') return json(200, RECURSO(estado.validado));
    if (ruta === '/asignaturas/a1/recursos/r1/validar') { estado.validado = true; return json(200, RECURSO(true)); }
    return json(404, { detail: 'no simulada' });
  });
  await page.goto(origin);
  // Esperar a que termine la consulta inicial de sesión (sin esto se ve «Cargando…»).
  await (sesion ? page.getByRole('heading', { name: '¿Qué quieres hacer hoy?' })
    : page.getByLabel('Usuario del SGA').or(page.getByLabel('Correo institucional'))).waitFor();
  return { context, page, estado };
}

test('ingreso con usuario y clave del SGA lleva al menú y no guarda la clave', async () => {
  const { context, page, estado } = await abrir({ sesion: false });
  const clave = page.getByLabel('Clave del SGA');
  assert.equal(await clave.getAttribute('type'), 'password');
  assert.equal(await clave.getAttribute('autocomplete'), 'current-password');
  assert.equal(await page.getByLabel('Usuario del SGA').getAttribute('autocomplete'), 'username');
  await page.getByLabel('Usuario del SGA').fill('docente');
  await clave.fill('secreta-123');
  await page.getByRole('button', { name: 'Ingresar' }).click();
  await page.getByRole('heading', { name: '¿Qué quieres hacer hoy?' }).waitFor();
  const envio = estado.llamadas.find(l => l.ruta === '/auth/ingresar');
  assert.deepEqual(JSON.parse(envio.cuerpo), { usuario: 'docente', clave: 'secreta-123' });
  const guardado = await page.evaluate(() => JSON.stringify([{ ...localStorage }, { ...sessionStorage }]));
  assert.ok(!guardado.includes('secreta-123'));
  await context.close();
});

test('clave incorrecta (401): mensaje genérico y la clave se borra', async () => {
  const { context, page } = await abrir({ sesion: false, rutas: {
    '/auth/ingresar': route => route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Usuario o clave incorrectos"}' }) } });
  await page.getByLabel('Usuario del SGA').fill('docente');
  await page.getByLabel('Clave del SGA').fill('mala');
  await page.getByRole('button', { name: 'Ingresar' }).click();
  await page.getByRole('alert').getByText('Usuario o clave incorrectos.').waitFor();
  assert.equal(await page.getByLabel('Clave del SGA').inputValue(), '');
  assert.equal(await page.getByLabel('Usuario del SGA').inputValue(), 'docente');
  await context.close();
});

test('demasiados intentos (429) muestra la espera de Retry-After', async () => {
  const { context, page } = await abrir({ sesion: false, rutas: {
    '/auth/ingresar': route => route.fulfill({ status: 429, headers: { 'Retry-After': '45' }, contentType: 'application/json', body: '{"detail":"Demasiados intentos"}' }) } });
  await page.getByLabel('Usuario del SGA').fill('docente');
  await page.getByLabel('Clave del SGA').fill('x');
  await page.getByRole('button', { name: 'Ingresar' }).click();
  await page.getByRole('alert').getByText('espera 45 s').waitFor();
  await context.close();
});

test('menú con tres pestañas y perfil docente en espera', async () => {
  const { context, page } = await abrir();
  const nav = page.getByRole('navigation', { name: 'Navegación principal' });
  for (const nombre of ['Inicio', 'Proyecto Formativo', 'Mis recursos']) {
    assert.equal(await nav.getByRole('button', { name: nombre, exact: true }).count(), 1, nombre);
  }
  const perfil = page.locator('section[aria-labelledby="camino-perfil"]');
  assert.equal(await perfil.getAttribute('aria-disabled'), 'true');
  assert.equal(await perfil.getByRole('button').count(), 0);
  assert.equal(await perfil.getByText('En espera').count(), 1);
  await context.close();
});

test('Empezar lista las materias del SGA y abrir una lleva a su menú', async () => {
  const { context, page } = await abrir();
  await page.getByRole('button', { name: 'Empezar' }).click();
  await page.getByRole('heading', { name: 'Generar herramientas' }).waitFor();
  const lista = page.getByRole('list', { name: 'Materias del SGA' });
  await lista.getByText('B26-SOFT-3 PARALELO 1').waitFor();
  assert.equal(await lista.getByRole('listitem').count(), 3);
  assert.equal(await page.locator('input[type="file"]').count(), 0);
  await lista.getByRole('button', { name: /ANALISIS DE DATOS/ }).click();
  await page.getByText('DISTRIBUCIONES').first().waitFor();
  await context.close();
});

test('materias no disponibles o inválidas salen desactivadas con su motivo', async () => {
  const { context, page } = await abrir();
  await page.getByRole('button', { name: 'Empezar' }).click();
  const lista = page.getByRole('list', { name: 'Materias del SGA' });
  await lista.getByText('B26-SOFT-3 PARALELO 2').waitFor();
  assert.equal(await lista.getByRole('button').count(), 1);
  const nd = lista.getByRole('listitem').filter({ hasText: 'ESTADISTICA' });
  assert.equal(await nd.locator('[aria-disabled="true"]').count(), 1);
  await nd.getByText('no está disponible').waitFor();
  await lista.getByRole('listitem').filter({ hasText: 'PROBABILIDAD' }).getByText('No se pudo importar').waitFor();
  await context.close();
});

test('un 401 a mitad del uso devuelve al ingreso', async () => {
  const { context, page, estado } = await abrir();
  estado.sesion = false;
  await page.route(url => url.pathname === '/api/asignaturas', route => route.fulfill({ status: 401, contentType: 'application/json', body: '{"detail":"Sesión requerida"}' }));
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Proyecto Formativo', exact: true }).click();
  await page.getByLabel('Usuario del SGA').waitFor();
  await context.close();
});

test('error al cargar las materias (503) se muestra con mensaje claro', async () => {
  const { context, page } = await abrir({ rutas: { '/materias': route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"x"}' }) } });
  await page.getByRole('button', { name: 'Empezar' }).click();
  await page.getByRole('alert').getByText('Servicio no disponible').waitFor();
  await context.close();
});

test('salir cierra la sesión', async () => {
  const { context, page } = await abrir();
  await page.getByRole('button', { name: 'Salir' }).click();
  await page.getByLabel('Usuario del SGA').waitFor();
  await context.close();
});

test('móvil: sin desbordamiento, menú colapsado y tarjetas apiladas', async () => {
  const { context, page } = await abrir({ viewport: { width: 360, height: 760 } });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('button', { name: 'Abrir navegación' }).click();
  await page.getByRole('navigation', { name: 'Navegación móvil' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('heading', { name: 'Mis recursos' }).waitFor();
  await context.close();
});

// --- P6b: Mis recursos ----------------------------------------------------------------

async function abrirAsignatura(page) {
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Proyecto Formativo', exact: true }).click();
  await page.getByRole('button', { name: 'Abrir ANALISIS DE DATOS' }).click();
  await page.getByRole('heading', { name: 'ANALISIS DE DATOS' }).waitFor();
}

test('recorrido: clase → actividad → generar → avance → recurso', async () => {
  const { context, page, estado } = await abrir();
  await abrirAsignatura(page);
  await page.getByText('Semana 2 · 12/10 – 18/10').waitFor();
  await page.getByRole('button', { name: /mié 14\/10 · Clase 1/ }).click();
  await page.getByRole('heading', { name: 'Clase 1 · Momento 2, sesión 1' }).waitFor();
  await page.getByText('Se permite IA como asistente.').waitFor();
  await page.getByLabel('Cuestionario').check();
  await page.getByRole('button', { name: 'Generar' }).click();
  await page.getByRole('heading', { name: 'Generando herramientas' }).waitFor();
  await page.getByText('Lista para revisar').waitFor();
  const consultas = estado.consultas;
  await page.getByRole('button', { name: 'Revisar' }).click();
  await page.getByRole('heading', { name: 'Cuestionario' }).waitFor();
  await page.waitForTimeout(4500);
  assert.equal(estado.consultas, consultas, 'la consulta de avance debe detenerse al terminar o salir');
  await context.close();
});

test('clase de un momento restringido muestra el aviso y no ofrece IA', async () => {
  const { context, page } = await abrir();
  await abrirAsignatura(page);
  await page.getByRole('button', { name: /Clase 2/ }).click();
  await page.getByRole('alert').getByText('excluye la IA').waitFor();
  assert.equal(await page.getByRole('checkbox').count(), 0);
  await page.getByText('No hay herramientas disponibles').waitFor();
  await context.close();
});

test('el menú ofrece clases y el Proyecto Formativo, no momentos', async () => {
  const { context, page } = await abrir();
  await abrirAsignatura(page);
  await page.getByRole('button', { name: 'Herramientas del Proyecto Formativo' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Herramientas del momento' }).count(), 0);
  assert.equal(await page.getByText(/Cierra el Momento/).count(), 0);
  await context.close();
});

test('validar con alertas pide confirmación y habilita la descarga', async () => {
  const { context, page } = await abrir();
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('button', { name: 'Revisar Cuestionario' }).click();
  await page.getByText('el revisor considera correctas las opciones 1 y 3').waitFor();
  assert.equal(await page.getByRole('link', { name: 'Descargar HTML para Canvas' }).count(), 0);
  assert.equal(await page.getByRole('link', { name: /Descargar PDF|Descargar Word/ }).count(), 0);
  await page.getByRole('button', { name: 'Validar recurso' }).click();
  await page.getByRole('dialog').getByText('¿Validar con alertas pendientes?').waitFor();
  await page.getByRole('button', { name: 'Validar de todos modos' }).click();
  const enlace = page.getByRole('link', { name: 'Descargar HTML para Canvas' });
  assert.ok((await page.getByRole('link', { name: 'Descargar PDF', exact: true }).getAttribute('href')).endsWith('formato=pdf'));
  assert.ok((await page.getByRole('link', { name: 'Descargar Word', exact: true }).getAttribute('href')).endsWith('formato=docx'));
  await enlace.waitFor();
  assert.match(await enlace.getAttribute('href'), /\/api\/asignaturas\/a1\/recursos\/r1\/exportar\?formato=html$/);
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  assert.equal(await page.getByRole('link', { name: /Descargar/ }).count(), 0);
  await page.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await enlace.waitFor();
  await context.close();
});

test('lector descarga los tres formatos sin editar ni validar', async () => {
  const json = body => route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  const { context, page } = await abrir({ rutas: {
    '/asignaturas': json([{ id: 'a1', nombre: 'ANALISIS DE DATOS', codigo_pf: 'B26-SOFT-3', version_silabo: '1.0', agente: 'ingenierias', rol: 'lector', dueno: 'otro@uti.edu.ec' }]),
    '/asignaturas/a1/menu': json({ id: 'a1', rol: 'lector', version_silabo: '1.0', menu: MENU_ASIG }),
    '/asignaturas/a1/recursos/r1': json(RECURSO(true)),
  } });
  await revisar(page, 'Cuestionario');
  await page.getByRole('link', { name: 'Descargar PDF', exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Editar', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Validar recurso', exact: true }).count(), 0);
  assert.equal(await page.getByRole('link', { name: /Descargar/ }).count(), 3);
  await context.close();
});

test('ficha: secciones en orden, con títulos legibles y sin claves internas', async () => {
  const { context, page } = await abrir();
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('button', { name: 'Revisar Ficha de clase' }).click();
  await page.getByRole('heading', { name: 'Ideas clave' }).waitFor();
  const titulos = await page.locator('main h3, main h4').allInnerTexts();
  assert.deepEqual(titulos.filter(t => t !== 'Paso 4 · Revisa el contenido' && !t.startsWith('Paso 5')),
    ['Ideas clave', 'Ejemplo resuelto', 'Enunciado', 'Pasos', 'Cómo se valora']);
  assert.equal(await page.locator('main ol li').count(), 2);
  await page.getByRole('columnheader', { name: 'Qué observar' }).waitFor();
  await page.getByRole('cell', { name: 'Cálculo correcto' }).waitFor();
  const texto = await page.locator('main').innerText();
  assert.ok(!/clase_id|numero_clase|Clase id|Numero clase/i.test(texto), 'no deben verse claves internas');
  await context.close();
});

/** Mis recursos → Revisar <nombre>. */
async function revisar(page, nombre) {
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('button', { name: `Revisar ${nombre}` }).click();
}

test('editar la ficha: cambia el texto, guarda y vuelve a «Sin validar»', async () => {
  const { context, page, estado } = await abrir();
  await revisar(page, 'Ficha de clase');
  await page.getByRole('button', { name: 'Editar' }).click();
  assert.equal(await page.getByText('Guarda o cancela la edición antes de validar.').count(), 1);
  await page.getByRole('textbox', { name: 'Enunciado' }).fill('Una cafetería mide sus ventas diarias.');
  await page.getByRole('textbox', { name: 'Pasos 2' }).fill('Interpretar la media');
  // Lo que viene de listas cerradas (tabla sin rutas) no se edita.
  assert.equal(await page.getByRole('textbox', { name: 'Qué observar 1' }).count(), 0);
  await page.getByRole('button', { name: 'Guardar cambios' }).click();
  await page.getByText('Cambios guardados').waitFor();
  const [{ ruta, cuerpo }] = estado.puts;
  assert.equal(ruta, '/asignaturas/a1/recursos/r2');
  assert.equal(cuerpo.revision, 0);
  assert.equal(cuerpo.contenido.aplicacion.ejemplo.enunciado, 'Una cafetería mide sus ventas diarias.');
  assert.deepEqual(cuerpo.contenido.aplicacion.ejemplo.pasos, ['Calcular la media', 'Interpretar la media']);
  assert.equal(cuerpo.contenido.aplicacion.clase_id, 'M2-S1', 'las claves internas viajan intactas');
  await page.getByText('Editado por el docente').waitFor();
  await page.getByRole('button', { name: 'Validar recurso' }).waitFor();
  await context.close();
});

test('editar pregunta: enunciado, clave y quitar (mínimo una)', async () => {
  const { context, page, estado } = await abrir();
  await revisar(page, 'Cuestionario');
  await page.getByRole('button', { name: 'Editar' }).click();
  await page.getByRole('textbox', { name: 'Pregunta 1: enunciado' }).fill('¿Qué prueba compara dos medias independientes?');
  await page.getByRole('textbox', { name: 'Pregunta 1: justificación B' }).fill('ANOVA compara tres o más grupos.');
  await page.getByRole('radio', { name: 'Pregunta 1: la clave es la opción C' }).check();
  assert.ok(await page.getByRole('button', { name: 'Quitar la pregunta 1' }).isDisabled(), 'no se puede quitar la única pregunta');
  await page.getByRole('button', { name: 'Guardar cambios' }).click();
  await page.getByText('Cambios guardados').waitFor();
  const [{ cuerpo }] = estado.puts;
  assert.equal(cuerpo.contenido[0].pregunta, '¿Qué prueba compara dos medias independientes?');
  assert.equal(cuerpo.contenido[0].opciones[1].justificacion, 'ANOVA compara tres o más grupos.');
  assert.equal(cuerpo.contenido[0].correcta, 2);
  await page.getByText('C) Chi cuadrado ✓ (clave)').waitFor();
  // Tras editar, las alertas del revisor ya no aplican: se avisa.
  await page.getByText('el revisor de IA no vuelve a revisar los cambios').waitFor();
  assert.equal(await page.getByText('el revisor considera correctas las opciones 1 y 3').count(), 0);
  await context.close();
});

test('si la API rechaza la edición (422) el borrador se conserva', async () => {
  const { context, page, estado } = await abrir();
  estado.falla422 = true;
  await revisar(page, 'Ficha de clase');
  await page.getByRole('button', { name: 'Editar' }).click();
  await page.getByRole('textbox', { name: 'Enunciado' }).fill('x');
  await page.getByRole('button', { name: 'Guardar cambios' }).click();
  await page.getByRole('alert').getByText('Revisa que ningún campo quede vacío o demasiado corto').waitFor();
  assert.equal(await page.getByRole('textbox', { name: 'Enunciado' }).inputValue(), 'x');
  await page.getByRole('button', { name: 'Cancelar' }).click();
  await page.getByText('Una tienda mide ventas.').waitFor();
  await context.close();
});

test('las herramientas sin IA no se editan', async () => {
  const { context, page } = await abrir();
  await revisar(page, 'Hoja de ruta del Proyecto Formativo');
  await page.getByRole('heading', { name: 'Producto final' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Editar' }).count(), 0);
  await context.close();
});

test('chat genera trabajos y permite seguir su avance y abrir el recurso', async () => {
  const { context, page } = await abrir({ rutas: {
    '/asignaturas/a1/chat': route => route.fulfill({ json: route.request().method() === 'POST'
      ? { id: 'p1', orden: 1, mensaje: 'Genera un cuestionario', estado: 'completado', respuesta: 'Se creó el trabajo.', recurso_id: null, revision_resultado: null, trabajos: ['t1'], creado: '2026-10-28T12:00:00Z' }
      : { pedidos: [], siguiente: null } }),
  } });
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('textbox', { name: 'Mensaje de ajuste' }).fill('Genera un cuestionario');
  await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).click();
  await page.getByRole('button', { name: 'Ver avance de generación', exact: true }).click();
  await page.getByRole('heading', { name: 'Generando herramientas' }).waitFor();
  await page.getByRole('button', { name: 'Revisar', exact: true }).click();
  await page.getByText('¿Qué prueba corresponde?').waitFor();
  await context.close();
});

test('recarga de chat tardía no cambia la revisión base del borrador manual', async () => {
  let soltar;
  const espera = new Promise(resolve => { soltar = resolve; });
  let avisoRecarga;
  const recarga = new Promise(resolve => { avisoRecarga = resolve; });
  let ajustado = false;
  let guardado;
  const { context, page } = await abrir({ rutas: {
    '/asignaturas/a1/recursos/r1': async route => {
      if (route.request().method() === 'PUT') {
        guardado = route.request().postDataJSON();
        return route.fulfill({ status: 409, json: { detail: 'El recurso cambió' } });
      }
      if (ajustado) { avisoRecarga(); await espera; }
      return route.fulfill({ json: { ...RECURSO(false), revision: ajustado ? 1 : 0 } });
    },
    '/asignaturas/a1/chat': route => {
      if (route.request().method() === 'POST') ajustado = true;
      return route.fulfill({ json: route.request().method() === 'POST'
        ? { id: 'p1', orden: 1, mensaje: 'Ajusta', estado: 'completado', respuesta: 'Aplicado', recurso_id: 'r1', revision_resultado: 1, trabajos: [], creado: '2026-10-28T12:00:00Z' }
        : { pedidos: [], siguiente: null } });
    },
  } });
  await revisar(page, 'Cuestionario');
  await page.getByRole('textbox', { name: 'Mensaje de ajuste' }).fill('Ajusta la pregunta');
  await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).click();
  await recarga;
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  soltar();
  const campo = page.getByRole('textbox', { name: 'Pregunta 1: enunciado' });
  await campo.fill('¿Qué procedimiento corresponde a la situación descrita?');
  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
  await page.getByText(/Tu borrador se conserva/).waitFor();
  assert.equal(guardado.revision, 0);
  assert.equal(await campo.inputValue(), '¿Qué procedimiento corresponde a la situación descrita?');
  await context.close();
});

/** API simulada con el modo de prueba encendido. */
const CON_MODO_PRUEBA = {
  '/auth/modo': route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ acceso_prueba: true }) }),
  '/auth/prueba': (route, estado) => {
    (estado.pruebas ??= []).push(JSON.parse(route.request().postData()));
    estado.sesion = true;
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ mensaje: 'Sesión iniciada' }) });
  },
};

test('modo de prueba: entrar solo con el correo, sin clave del SGA', async () => {
  const { context, page, estado } = await abrir({ sesion: false, rutas: CON_MODO_PRUEBA });
  await page.getByText('Modo de prueba: cualquiera puede entrar').waitFor();
  assert.equal(await page.getByLabel('Clave del SGA').count(), 0);
  await page.getByLabel('Correo institucional').fill('docente@uti.edu.ec');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await page.getByRole('heading', { name: '¿Qué quieres hacer hoy?' }).waitFor();
  assert.deepEqual(estado.pruebas, [{ correo: 'docente@uti.edu.ec' }]);
  await context.close();
});

test('modo de prueba: entrar como invitado sin escribir correo', async () => {
  const { context, page, estado } = await abrir({ sesion: false, rutas: CON_MODO_PRUEBA });
  await page.getByRole('button', { name: 'Entrar como invitado' }).click();
  await page.getByRole('heading', { name: '¿Qué quieres hacer hoy?' }).waitFor();
  assert.deepEqual(estado.pruebas, [{}]);
  await context.close();
});

test('sin modo de prueba el ingreso pide usuario y clave del SGA', async () => {
  const { context, page } = await abrir({ sesion: false });
  await page.getByLabel('Clave del SGA').waitFor();
  assert.equal(await page.getByRole('button', { name: 'Entrar como invitado' }).count(), 0);
  await context.close();
});

test('Mis recursos muestra lo que sigue generándose y explica la espera', async () => {
  const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  const { context, page, estado } = await abrir({ rutas: {
    '/asignaturas/a1/trabajos': (route, e) => {
      e.consultas = (e.consultas ?? 0) + 1;
      const fin = e.consultas > 1;
      return json(route, [{ id: 't9', herramienta: 'cuestionario', ambito_tipo: 'clase', ambito_id: 'M1-S1', lotes_total: 0, lotes_hechos: 0,
        error: null, estado: fin ? 'listo' : 'en_cola', recurso_id: fin ? 'r1' : null }]);
    },
  } });
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByText('En curso', { exact: true }).waitFor();
  await page.getByText('Se genera una herramienta a la vez por Proyecto Formativo').waitFor();
  await page.getByText('En espera', { exact: true }).waitFor();
  // Al terminar desaparece y la tabla se recarga sola.
  const recargas = () => estado.llamadas.filter(l => l.ruta === '/asignaturas/a1/recursos').length;
  const antes = recargas();
  await page.getByText('En curso', { exact: true }).waitFor({ state: 'detached', timeout: 7000 });
  assert.ok(recargas() > antes, 'la tabla debe recargarse al terminar un trabajo');
  await context.close();
});

test('Mis recursos: una sola acción por fila, validar o descargar, sin estados técnicos', async () => {
  const { context, page } = await abrir();
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  const tabla = page.getByRole('table', { name: 'Recursos del Proyecto Formativo' });
  await tabla.getByText('Por validar').first().waitFor();
  await tabla.getByText('Validada').waitFor();
  const filaPendiente = tabla.getByRole('row').filter({ hasText: 'Cuestionario' });
  await filaPendiente.getByRole('button', { name: 'Revisar Cuestionario' }).waitFor();
  assert.equal(await filaPendiente.getByRole('link').count(), 0, 'sin validar no se descarga');
  const filaValidada = tabla.getByRole('row').filter({ hasText: 'Hoja de ruta' });
  for (const [etiqueta, formato] of [['HTML', 'html'], ['PDF', 'pdf'], ['Word', 'docx']]) {
    const enlace = filaValidada.getByRole('link', { name: new RegExp(`en ${etiqueta}$`) });
    assert.match(await enlace.getAttribute('href'), new RegExp(`recursos/r3/exportar\\?formato=${formato}$`));
  }
  const texto = await tabla.innerText();
  assert.ok(!/Requiere revisión|Listo\b|Borrador|lote/i.test(texto), 'no deben verse estados internos');
  await context.close();
});

test('la interfaz dice Proyecto Formativo, no asignatura', async () => {
  const { context, page } = await abrir();
  const nav = page.getByRole('navigation', { name: 'Navegación principal' });
  await nav.getByRole('button', { name: 'Proyecto Formativo', exact: true }).click();
  await page.getByRole('heading', { name: 'Proyecto Formativo' }).waitFor();
  assert.ok(!/asignatura/i.test(await page.locator('body').innerText()));
  await nav.getByRole('button', { name: 'Mis recursos', exact: true }).click();
  await page.getByRole('table', { name: 'Recursos del Proyecto Formativo' }).waitFor();
  assert.ok(!/asignatura/i.test(await page.locator('body').innerText()));
  await context.close();
});

test('Mis recursos solo lista resultados finales: nada de momentos, y de rúbricas solo la final', async () => {
  const fila = (id, ambito_id, herramienta) => ({ id, trabajo_id: `t${id}`, ambito_id, herramienta, version_silabo: '1.0', estado: 'listo',
    revision: 0, creado: '2026-11-04T10:00:00Z', validado: false });
  const { context, page } = await abrir({ rutas: {
    '/asignaturas/a1/recursos': route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([
      fila('a', 'M3', 'simulacro'), fila('b', 'M1', 'rubrica_momento'), fila('c', 'M2', 'guia_evidencia'),
      fila('d', 'asignatura', 'rubrica_final'), fila('e', 'M1-S1', 'ficha_clase')]) }),
  } });
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  const tabla = page.getByRole('table', { name: 'Recursos del Proyecto Formativo' });
  await tabla.getByText('Rúbrica del producto final').waitFor();
  await tabla.getByText('Ficha de clase').waitFor();
  for (const oculto of ['Simulacro', 'Rúbrica del momento', 'Guía de la evidencia']) {
    assert.equal(await tabla.getByText(oculto).count(), 0, oculto);
  }
  await context.close();
});

test('sin códigos: clases y momentos con nombres completos', async () => {
  const { context, page } = await abrir();
  const nav = page.getByRole('navigation', { name: 'Navegación principal' });
  await nav.getByRole('button', { name: 'Mis recursos', exact: true }).click();
  const tabla = page.getByRole('table', { name: 'Recursos del Proyecto Formativo' });
  await tabla.getByText('Momento 2, sesión 1').first().waitFor();
  assert.ok(!/\bM\d+(-S\d+)?\b/.test(await tabla.innerText()));
  await context.close();
});

test('avisa si la clave contradice su explicación, también en lo ya validado', async () => {
  const conAlerta = { ...RECURSO(false), evidencia: {}, revision_claves: { i1: ['la explicación de la respuesta marcada como correcta dice que está equivocada; revisa la clave'] } };
  const { context, page } = await abrir({ rutas: {
    '/asignaturas/a1/recursos/r1': route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(conAlerta) }),
  } });
  await revisar(page, 'Cuestionario');
  await page.getByText('dice que está equivocada; revisa la clave').waitFor();
  await page.getByText('1 alerta', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Validar recurso' }).click();
  await page.getByText('¿Validar con alertas pendientes?').waitFor();
  await context.close();
});

test('dos apartados: el estudiante sin respuestas y el docente con ellas', async () => {
  const fila = (id, herramienta) => ({ id, trabajo_id: `t${id}`, ambito_id: 'M2-S1', herramienta, version_silabo: '1.0', estado: 'listo',
    revision: 0, creado: '2026-11-04T10:00:00Z', validado: true });
  const { context, page } = await abrir({ rutas: {
    '/asignaturas/a1/recursos': route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([fila('q', 'cuestionario'), fila('f', 'ficha_clase')]) }),
  } });
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Mis recursos', exact: true }).click();
  const tabla = page.getByRole('table', { name: 'Recursos del Proyecto Formativo' });
  const quiz = tabla.getByRole('row').filter({ hasText: 'Cuestionario' });
  await quiz.getByText('Docente (respuestas):').waitFor();
  assert.ok(!/version=docente/.test(await quiz.getByRole('link', { name: 'Descargar Cuestionario en PDF' }).getAttribute('href')));
  assert.match(await quiz.getByRole('link', { name: 'Descargar respuestas de Cuestionario en PDF' }).getAttribute('href'), /formato=pdf&version=docente$/);
  assert.equal(await quiz.getByRole('link', { name: /respuestas de Cuestionario en HTML/ }).count(), 0);
  assert.equal(await tabla.getByRole('row').filter({ hasText: 'Ficha de clase' }).getByText('Docente (respuestas):').count(), 0, 'la ficha no tiene respuestas');
  await context.close();
});
