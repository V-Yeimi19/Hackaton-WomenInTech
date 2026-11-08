// Uso: backend en http://localhost:8000 (docker compose up), mock servido en :5500 y luego: node tests/e2e-api.mjs
// E2E del prototipo contra el backend real (FastAPI + PostgreSQL) con Edge headless (CDP).
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9335;
const APP = "http://127.0.0.1:5500/index.html?api=http://localhost:8000";
const API = "http://localhost:8000/api/v1";
const proc = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "edge-api-"))}`,
  "--window-size=1200,950", "--no-first-run", "about:blank"], { stdio: "ignore" });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
const logs = [];
const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
async function evaluate(expr) {
  const r = await send("Runtime.evaluate", { expression: `(async () => { ${expr} })()`, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}
let fails = 0;
const check = (name, ok, info = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  — " + info : ""}`); if (!ok) fails++; };
const H = `
  const f = () => document.getElementById("screen").contentDocument;
  const click = el => el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: el.ownerDocument.defaultView }));
  const apiGet = async p => (await fetch("${API}" + p, { headers: { Authorization: "Bearer " + JSON.parse(localStorage.getItem("mica-session")).token } })).json();
`;
const phone = () => "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");

async function uiLogin(num) {
  await evaluate(`${H} click(f().getElementById("btn-start"));`);
  await sleep(300);
  await evaluate(`${H} const d=f(); d.getElementById("phone").value="${num}"; d.getElementById("login-form").requestSubmit();`);
  await sleep(4000);
}

try {
  let t;
  for (let i = 0; i < 40 && !t; i++) { await sleep(250); try { t = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find(x => x.type === "page"); } catch {} }
  ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener("open", r));
  ws.addEventListener("message", e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result || {}); pending.delete(m.id); }
    if (m.method === "Runtime.exceptionThrown") logs.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: APP });
  await sleep(2500);
  await evaluate(`localStorage.clear(); sessionStorage.clear();`);
  await send("Page.navigate", { url: APP });
  await sleep(3500);

  // 1. Login contra la API
  const num = phone();
  await uiLogin(num);
  const sess = await evaluate(`return JSON.parse(localStorage.getItem("mica-session"));`);
  check("Login en modo API", sess && sess.mode === "api" && !!sess.token, JSON.stringify({ mode: sess && sess.mode }));
  check("Entra a Inicio", (await evaluate(`return location.hash;`)) === "#home");
  const api1 = await evaluate(`${H} return await apiGet("/wallets");`);
  const ui1 = await evaluate(`return Mica.state.wallets;`);
  check("Saldos de la UI = saldos del servidor",
    Number(api1.items[0].balance) === ui1.principal.balance && Number(api1.items[1].balance) === ui1.cafe.balance && Number(api1.items[2].balance) === ui1.vacaciones.balance,
    JSON.stringify(api1.items.map(w => w.balance)));
  const movs = await evaluate(`return Mica.state.txs.length;`);
  check("Movimientos del servidor cargados", movs === 9, String(movs));

  // 2. Yapeo desde el negocio con categoría
  await evaluate(`${H} click(f().getElementById("bar-yapear"));`); await sleep(600);
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="cafe"]'));`); await sleep(2500);
  await evaluate(`${H} const d=f(); ["1","2",".","0","5"].forEach(x=>click(d.querySelector('.pad-key[data-key="'+x+'"]'))); click(d.querySelector('[data-category^="📦"]'));`);
  const rec = (await evaluate(`${H} return f().getElementById("recipient-name").firstChild.textContent;`)).trim();
  await evaluate(`${H} click(f().getElementById("pay-submit-btn"));`); await sleep(4000);
  const cons = await evaluate(`${H} const d=f(); return { hash: location.hash, amount: d.querySelector("[class*='text-[42px]']")?.textContent, text: d.body.innerText };`);
  const last = await evaluate(`${H} return (await apiGet("/movements?limit=1")).items[0];`);
  check("Constancia tras yapear", cons.hash === "#constancia-negocio" && cons.amount === "12.05", cons.hash);
  check("Nro. de operación = servidor", cons.text.includes(last.operation_number), last.operation_number);
  check("Código de seguridad = servidor", cons.text.replace(/\s+/g, "").includes(last.security_code.split("").join("")), last.security_code);
  check("Movimiento en el servidor con categoría", last.title === "Yapeo a " + rec && last.category === "RESTOCK" && last.amount === "-12.05", JSON.stringify({ t: last.title, c: last.category }));
  const api2 = await evaluate(`${H} return await apiGet("/wallets");`);
  check("Saldo del negocio bajó en el servidor", (Number(api1.items[1].balance) - Number(api2.items[1].balance)).toFixed(2) === "12.05");

  // 3. Límite por yapeo (servidor y cliente)
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => /Nuevo yapeo/.test(b.innerText)));`); await sleep(3000);
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="principal"]'));`); await sleep(2500);
  await evaluate(`${H} const d=f(); ["6","0","0"].forEach(x=>click(d.querySelector('.pad-key[data-key="'+x+'"]'))); click(d.getElementById("pay-submit-btn"));`); await sleep(500);
  check("Bloquea más de S/ 500", (await evaluate(`return document.getElementById("toast").textContent;`)).includes("500"));
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.getAttribute("aria-label") === "Cerrar"));`); await sleep(2500);

  // 4. Transferencia entre billeteras
  await evaluate(`${H} click(f().getElementById("btn-transfer"));`); await sleep(600);
  await evaluate(`${H} click(f().querySelector('#wallet-transfer [data-toggle="from"]'));`); await sleep(200);
  await evaluate(`${H} click(f().querySelector('#wallet-transfer [data-pick="from:cafe"]'));`); await sleep(200);
  await evaluate(`${H} click(f().querySelector('#wallet-transfer [data-toggle="to"]'));`); await sleep(200);
  await evaluate(`${H} click(f().querySelector('#wallet-transfer [data-pick="to:vacaciones"]'));`); await sleep(200);
  await evaluate(`${H} const d=f(); const a=d.querySelector("#wallet-transfer [data-amount]"); a.value="10"; a.dispatchEvent(new Event("input",{bubbles:true}));
    const n=d.querySelector("#wallet-transfer [data-note]"); n.value="Prueba E2E"; n.dispatchEvent(new Event("input",{bubbles:true}));`);
  await evaluate(`${H} click(f().querySelector('#wallet-transfer [data-act="send"]'));`); await sleep(3500);
  const api3 = await evaluate(`${H} return await apiGet("/wallets");`);
  check("Transferencia en el servidor",
    (Number(api2.items[1].balance) - Number(api3.items[1].balance)).toFixed(2) === "10.00" &&
    (Number(api3.items[2].balance) - Number(api2.items[2].balance)).toFixed(2) === "10.00",
    JSON.stringify(api3.items.map(w => w.balance)));
  const tr = await evaluate(`${H} return (await apiGet("/movements?limit=1")).items[0];`);
  check("Transferencia con descripción", tr.direction === "TRANSFER" && tr.note === "Prueba E2E");

  // 4b. Pago con QR: escanear -> elegir billetera -> monto -> constancia
  await evaluate(`${H} click(f().getElementById("bar-scan"));`); await sleep(2500);
  await evaluate(`${H} click(f().getElementById("cameraFeedSim").parentElement);`); await sleep(1200);
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="principal"]'));`); await sleep(2500);
  const qrRec = (await evaluate(`${H} return f().getElementById("recipient-name").firstChild.textContent;`)).trim();
  await evaluate(`${H} const d=f(); ["7"].forEach(x=>click(d.querySelector('.pad-key[data-key="'+x+'"]'))); click(d.getElementById("pay-submit-btn"));`); await sleep(4000);
  const qr = await evaluate(`${H} return (await apiGet("/movements?limit=1")).items[0];`);
  check("Pago con QR en el servidor", qr.title === "Yapeo a " + qrRec && qr.amount === "-7.00" && qr.from_wallet.name === "Principal" && qr.category === null, JSON.stringify({ t: qr.title, a: qr.amount }));
  check("Constancia del QR", (await evaluate(`return location.hash;`)) === "#constancia");
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.innerText.trim() === "close"));`); await sleep(2500);
  const apiQr = await evaluate(`${H} return await apiGet("/wallets");`);

  // 5. Crear billetera
  await evaluate(`${H} click([...f().querySelectorAll(".snap-center, [class*='cursor-pointer']")].find(x => /Nueva Billetera/.test(x.innerText)));`); await sleep(2500);
  await evaluate(`${H} const d=f(); const i=d.getElementById("name"); i.value="Mi Bodega Prueba"; i.dispatchEvent(new Event("input",{bubbles:true})); d.getElementById("form").requestSubmit();`);
  await sleep(4000);
  const api4 = await evaluate(`${H} return await apiGet("/wallets");`);
  const custom = api4.items.find(w => w.role === "CUSTOM");
  check("Billetera creada en el servidor", custom && custom.name === "Mi Bodega Prueba" && custom.balance === "0.00");
  check("Inicio muestra la billetera nueva", (await evaluate(`${H} return location.hash + "|" + f().body.innerText.includes("Mi Bodega Prueba");`)) === "#home-nueva|true");

  // 6. Eliminar la billetera creada (saldo 0)
  await evaluate(`${H} const card=[...f().querySelectorAll(".snap-center")].find(c => c.innerText.includes("Mi Bodega Prueba")); click(card.querySelector('[aria-label="Opciones de billetera"]'));`); await sleep(600);
  await evaluate(`${H} click(f().querySelector('#wallet-options [data-act="ask-delete"]'));`); await sleep(300);
  await evaluate(`${H} click(f().querySelector('#wallet-options [data-act="confirm"]'));`); await sleep(4000);
  const api5 = await evaluate(`${H} return await apiGet("/wallets");`);
  check("Billetera archivada en el servidor", !api5.items.some(w => w.role === "CUSTOM") && (await evaluate(`return location.hash;`)) === "#home");
  check("Saldos intactos tras eliminar billetera sin saldo", JSON.stringify(api5.items.map(w => w.balance)) === JSON.stringify(apiQr.items.map(w => w.balance)));

  // 7. Movimientos: tocar el yapeo abre su constancia con el mismo número
  await evaluate(`${H} if (f().getElementById("mov-panel").classList.contains("hidden")) click(f().getElementById("mov-toggle"));`); await sleep(1500);
  const row = await evaluate(`${H} const r=[...f().querySelectorAll("#tx-container .tx-item")].find(r => r.innerText.includes("Yapeo a " + ${JSON.stringify(rec)})); return r && r.innerText.split(String.fromCharCode(10)).join(" ");`);
  check("Movimiento con descripción en Inicio", !!row && row.includes("Para volver a surtir") && row.includes("12.05"), row);
  await evaluate(`${H} click([...f().querySelectorAll("#tx-container .tx-item")].find(r => r.innerText.includes("Yapeo a " + ${JSON.stringify(rec)})));`); await sleep(2500);
  check("Constancia desde movimiento = servidor", (await evaluate(`${H} return f().body.innerText;`)).includes(last.operation_number));
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.innerText.trim() === "close"));`); await sleep(2500);

  // 8. Cerrar sesión (menú lateral) invalida el token en el servidor
  const token = (await evaluate(`return JSON.parse(localStorage.getItem("mica-session")).token;`));
  await evaluate(`${H} click(f().querySelector('#top-home [aria-label="Mi perfil"]'));`); await sleep(500);
  await evaluate(`${H} click([...f().querySelectorAll("#side-menu button")].find(b => b.innerText.includes("Cerrar sesión")));`); await sleep(2500);
  check("Vuelve al login", (await evaluate(`return location.hash;`)) === "#login");
  const status = await evaluate(`return (await fetch("${API}/wallets", { headers: { Authorization: "Bearer ${token}" } })).status;`);
  check("Token revocado en el servidor", status === 401, String(status));

  // 9. Mismo número: mismos datos (persistidos); otro número: otros datos
  await uiLogin(num);
  const again = await evaluate(`${H} return await apiGet("/wallets");`);
  check("Mismo número conserva sus datos", JSON.stringify(again.items.map(w => w.balance)) === JSON.stringify(api5.items.map(w => w.balance)));
  await evaluate(`Mica.logout();`); await sleep(1500);
  await uiLogin(phone());
  const other = await evaluate(`${H} return await apiGet("/wallets");`);
  check("Otro número, otros saldos", JSON.stringify(other.items.map(w => w.balance)) !== JSON.stringify(again.items.map(w => w.balance)));

  check("Sin errores de JS", logs.length === 0, logs.join(" | "));
} catch (e) {
  console.log("ERROR", e.message); fails++;
} finally {
  try { ws?.close(); } catch {}
  proc.kill();
  console.log(fails ? `\n${fails} fallo(s)` : "\nTODO OK");
  process.exit(fails ? 1 : 0);
}
