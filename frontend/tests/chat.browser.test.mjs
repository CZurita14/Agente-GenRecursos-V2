import { before, after, test } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright';

let browser;
let server;
const origin = 'http://127.0.0.1:4193';
before(async () => {
  server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4193', '--strictPort']);
  let salida = '';
  server.stdout.on('data', c => { salida += c; });
  server.stderr.on('data', c => { salida += c; });
  let listo = false;
  let diagnostico = '';
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null) throw Error(salida);
    try { const res = await fetch(origin); listo = res.ok; if (!listo) diagnostico = `${res.status}: ${await res.text()}`; } catch (e) { diagnostico = String(e.cause ?? e); }
    if (listo) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(listo, `${salida}\n${diagnostico}`);
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
});
after(async () => { await browser?.close(); server?.kill(); });

const pedido = (cambios = {}) => ({ id: 'p1', orden: 1, mensaje: 'Ajusta pregunta 3', estado: 'en_cola', respuesta: null,
  recurso_id: 'r1', revision_resultado: null, trabajos: [], creado: '2026-10-28T12:00:00Z', ...cambios });

async function abrir(api, reloj = false) {
  const page = await browser.newPage();
  if (reloj) await page.clock.install();
  await page.route(url => url.pathname.startsWith('/api/'), api);
  // Montaje aislado: no requiere cambios en App ni en Recurso.
  await page.route(origin + '/', route => route.fulfill({ contentType: 'text/html', body: '<div id="chat-test"></div>' }));
  await page.goto(origin);
  await page.evaluate(async () => {
    const { default: RefreshRuntime } = await import('/@react-refresh');
    RefreshRuntime.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => type => type;
    window.__vite_plugin_react_preamble_installed__ = true;
    const { default: React } = await import('/node_modules/.vite/deps/react.js');
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js');
    const { ChatAjustes } = await import('/src/components/ChatAjustes.tsx');
    const root = ReactDOM.createRoot(document.getElementById('chat-test'));
    window.actualizaciones = 0;
    window.sesionesVencidas = 0;
    window.trabajosAbiertos = [];
    let props = { aid: 'a1', rid: 'r1', revision: 0, onActualizado: () => window.actualizaciones++, onSesionVencida: () => window.sesionesVencidas++, onTrabajos: ids => window.trabajosAbiertos.push(ids) };
    window.montarChat = cambios => { props = { ...props, ...cambios }; root.render(React.createElement(React.StrictMode, null, React.createElement(ChatAjustes, props))); };
    window.montarChat({});
  });
  return page;
}
const vacio = route => route.fulfill({ json: { pedidos: [], siguiente: null } });

test('envío por teclado, UUID retenido tras fallo, bloqueo doble y texto escapado', async () => {
  const cuerpos = [];
  const page = await abrir(async route => {
    if (route.request().method() !== 'POST') return vacio(route);
    cuerpos.push(route.request().postDataJSON());
    if (cuerpos.length === 1) return route.abort('failed');
    await new Promise(resolve => setTimeout(resolve, 100));
    await route.fulfill({ status: 202, json: pedido({ estado: 'completado', respuesta: '<img src=x onerror=alert(1)>', revision_resultado: 1 }) });
  });
  try {
    const campo = page.getByRole('textbox', { name: 'Mensaje de ajuste' });
    await campo.fill('<script>alert(1)</script>');
    assert.equal(await campo.getAttribute('maxlength'), '2000');
    await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.getByRole('button', { name: 'Reintentar envío' }).waitFor();
    assert.ok(await campo.isDisabled());
    await page.evaluate(() => {
      const form = document.querySelector('form');
      form.requestSubmit();
      form.requestSubmit();
    });
    await page.getByText('Revisión 1.', { exact: false }).waitFor();
    assert.equal(cuerpos.length, 2);
    assert.deepEqual(cuerpos[0], cuerpos[1]);
    assert.equal(cuerpos[0].revision, 0);
    assert.equal(cuerpos[0].recurso_id, 'r1');
    assert.match(cuerpos[0].peticion_id, /^[0-9a-f-]{36}$/);
    assert.equal(await page.locator('ol img, ol script').count(), 0);
    await page.waitForFunction(() => window.actualizaciones === 1);
  } finally { await page.close(); }
});

test('consulta pendiente y difiere refresco durante edición manual', async () => {
  let consultas = 0;
  const page = await abrir(async route => {
    if (new URL(route.request().url()).pathname.endsWith('/p1')) {
      consultas++;
      return route.fulfill({ json: pedido({ estado: 'completado', respuesta: 'Aplicado', revision_resultado: 1 }) });
    }
    return route.fulfill({ json: { pedidos: [pedido()], siguiente: null } });
  });
  try {
    await page.getByText('En cola', { exact: true }).waitFor();
    await page.evaluate(() => window.montarChat({ deshabilitado: true }));
    await page.getByText('Aplicado', { exact: false }).waitFor();
    assert.equal(await page.evaluate(() => window.actualizaciones), 0);
    assert.ok(await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).isDisabled());
    await page.evaluate(() => window.montarChat({ deshabilitado: false }));
    await page.waitForFunction(() => window.actualizaciones === 1);
    assert.equal(consultas, 1);
  } finally { await page.close(); }
});

test('cambiar aid y rid limpia borrador y descarta historial tardío', async () => {
  const page = await abrir(async route => {
    const aid = new URL(route.request().url()).pathname.split('/')[3];
    if (aid === 'a1') {
      await new Promise(resolve => setTimeout(resolve, 500));
      return route.fulfill({ json: { pedidos: [pedido({ mensaje: 'HISTORIAL ANTIGUO' })], siguiente: null } }).catch(() => {});
    }
    return vacio(route);
  });
  try {
    await page.getByRole('textbox').fill('borrador privado');
    await page.evaluate(() => window.montarChat({ aid: 'a2', rid: 'r2' }));
    await page.waitForFunction(() => document.querySelector('textarea')?.value === '');
    await page.waitForTimeout(650);
    assert.equal(await page.getByText('HISTORIAL ANTIGUO').count(), 0);
    await page.getByRole('textbox').fill('otro borrador');
    await page.evaluate(() => window.montarChat({ rid: 'r3' }));
    await page.waitForFunction(() => document.querySelector('textarea')?.value === '');
  } finally { await page.close(); }
});

test('timeout permite reanudar seguimiento sin reenviar; conflicto difiere refresco durante edición', async () => {
  let consultas = 0;
  const page = await abrir(async route => {
    if (new URL(route.request().url()).pathname.endsWith('/p1')) {
      consultas++;
      return route.fulfill({ json: pedido({ estado: consultas > 1 ? 'conflicto' : 'procesando' }) });
    }
    return route.fulfill({ json: { pedidos: [pedido()], siguiente: null } });
  }, true);
  try {
    await page.getByText('En cola', { exact: true }).waitFor();
    await page.clock.runFor(1000);
    await page.getByText('Procesando', { exact: true }).waitFor();
    await page.clock.runFor(1500);
    assert.equal(consultas, 1, 'el siguiente intento espera el backoff de dos segundos');
    await page.clock.fastForward(120_000);
    await page.getByRole('button', { name: 'Consultar estado de nuevo' }).waitFor();
    await page.evaluate(() => window.montarChat({ deshabilitado: true }));
    await page.getByRole('button', { name: 'Consultar estado de nuevo' }).click();
    await page.clock.runFor(1000);
    await page.getByText('Conflicto:', { exact: false }).waitFor();
    assert.equal(await page.evaluate(() => window.actualizaciones), 0);
    await page.evaluate(() => window.montarChat({ deshabilitado: false }));
    await page.waitForFunction(() => window.actualizaciones === 1);
  } finally { await page.close(); }
});

for (const estado of [409, 422]) {
  test(`POST ${estado} libera compositor y UUID para corregir; refresco solo tras terminar edición`, async () => {
    const cuerpos = [];
    let rechazar;
    const rechazoPendiente = new Promise(resolve => { rechazar = resolve; });
    const page = await abrir(async route => {
      if (route.request().method() !== 'POST') return vacio(route);
      cuerpos.push(route.request().postDataJSON());
      if (cuerpos.length === 1) {
        await rechazoPendiente;
        return route.fulfill({ status: estado, json: { detail: 'Corrige el pedido.' } });
      }
      return route.fulfill({ status: 202, json: pedido({ estado: 'completado', respuesta: 'Pedido corregido' }) });
    });
    try {
      const campo = page.getByRole('textbox', { name: 'Mensaje de ajuste' });
      await campo.fill('Mensaje original');
      await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('form button')?.disabled);
      await page.evaluate(() => window.montarChat({ deshabilitado: true }));
      await page.getByText('Guarda o cancela la edición manual', { exact: false }).waitFor();
      rechazar();
      await page.getByRole('alert').waitFor();
      assert.equal(await page.evaluate(() => window.actualizaciones), 0);
      await page.evaluate(() => window.montarChat({ deshabilitado: false, revision: 2 }));
      await page.waitForFunction(() => !document.querySelector('textarea')?.disabled);
      assert.equal(await campo.inputValue(), 'Mensaje original');
      if (estado === 409) await page.waitForFunction(() => window.actualizaciones === 1);
      else assert.equal(await page.evaluate(() => window.actualizaciones), 0);
      await campo.fill('Mensaje corregido');
      await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).click();
      await page.getByText('Pedido corregido', { exact: false }).waitFor();
      assert.equal(cuerpos.length, 2);
      assert.notEqual(cuerpos[0].peticion_id, cuerpos[1].peticion_id);
      assert.equal(cuerpos[1].mensaje, 'Mensaje corregido');
      assert.equal(cuerpos[1].revision, 2);
    } finally { rechazar(); await page.close(); }
  });
}

for (const estado of [429, 503]) {
  test(`POST ${estado} conserva el cuerpo y UUID pese a cambiar la revisión del padre`, async () => {
    const cuerpos = [];
    const page = await abrir(async route => {
      if (route.request().method() !== 'POST') return vacio(route);
      cuerpos.push(route.request().postDataJSON());
      if (cuerpos.length === 1) return route.fulfill({ status: estado, json: {} });
      return route.fulfill({ status: 202, json: pedido({ estado: 'completado', respuesta: 'Recuperado' }) });
    });
    try {
      await page.getByRole('textbox').fill('Ajuste original');
      await page.getByRole('button', { name: 'Enviar ajuste', exact: true }).click();
      await page.getByRole('button', { name: 'Reintentar envío' }).waitFor();
      assert.ok(await page.getByRole('textbox').isDisabled());
      await page.evaluate(() => window.montarChat({ revision: 2 }));
      await page.getByRole('button', { name: 'Reintentar envío' }).click();
      await page.getByText('Recuperado', { exact: false }).waitFor();
      assert.deepEqual(cuerpos[1], cuerpos[0]);
    } finally { await page.close(); }
  });
}

test('avance de generación requiere acción por teclado, respeta borrador y callback opcional', async () => {
  const ids = ['trabajo-uno', 'trabajo-dos'];
  const page = await abrir(route => route.fulfill({ json: { pedidos: [pedido({ estado: 'completado', trabajos: ids })], siguiente: null } }));
  try {
    const boton = page.getByRole('button', { name: 'Ver avance de generación', exact: true });
    await boton.waitFor();
    assert.equal(await page.getByText('trabajo-uno', { exact: false }).count(), 0);
    await page.evaluate(() => window.montarChat({ deshabilitado: true }));
    await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent === 'Ver avance de generación')?.disabled);
    assert.deepEqual(await page.evaluate(() => window.trabajosAbiertos), []);
    await page.evaluate(() => window.montarChat({ deshabilitado: false }));
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(b => b.textContent === 'Ver avance de generación')?.disabled);
    await boton.focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => window.trabajosAbiertos.length === 1);
    assert.deepEqual(await page.evaluate(() => window.trabajosAbiertos), [ids]);
    await page.evaluate(() => window.montarChat({ onTrabajos: undefined }));
    await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent === 'Ver avance de generación')?.disabled);
  } finally { await page.close(); }
});

test('401 invoca sesión vencida y no muestra detalles internos', async () => {
  const page = await abrir(route => route.fulfill({ status: 401, json: { detail: 'SECRETO INTERNO' } }));
  try {
    await page.waitForFunction(() => window.sesionesVencidas > 0);
    assert.equal(await page.getByText('SECRETO INTERNO').count(), 0);
  } finally { await page.close(); }
});
