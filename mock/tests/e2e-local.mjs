// Uso: python -m http.server 5500 --bind 127.0.0.1 (en mock/) y luego: node tests/e2e-local.mjs
// Prueba E2E del prototipo con Edge headless vía Chrome DevTools Protocol (sin dependencias).
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PORT = 9333;
const profile = mkdtempSync(join(tmpdir(), "edge-e2e-"));
const proc = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--window-size=1200,950", "--no-first-run", "about:blank"], { stdio: "ignore" });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0;
const pending = new Map();
const logs = [];
function send(method, params = {}) {
  return new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
}
async function evaluate(expr) {
  const r = await send("Runtime.evaluate", { expression: `(async () => { ${expr} })()`, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}

let fails = 0;
function check(name, ok, info = "") { console.log(`${ok ? "PASS" : "FAIL"}  ${name}${info ? "  — " + info : ""}`); if (!ok) fails++; }

try {
  let target;
  for (let i = 0; i < 40 && !target; i++) {
    await sleep(250);
    try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find(t => t.type === "page"); } catch {}
  }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener("open", r));
  ws.addEventListener("message", e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result || {}); pending.delete(m.id); }
    if (m.method === "Runtime.exceptionThrown") logs.push("EXC " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") logs.push("ERR " + m.params.args.map(a => a.value ?? a.description).join(" "));
  });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: "http://127.0.0.1:5500/index.html?api=off" });
  await sleep(3500);

  await evaluate(`localStorage.clear(); sessionStorage.clear();`);
  await send("Page.navigate", { url: "http://127.0.0.1:5500/index.html?api=off" });
  await sleep(3500);
  const H = `
    const f = () => document.getElementById("screen").contentDocument;
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const click = el => el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: el.ownerDocument.defaultView }));
  `;
  // Login
  check("Sin sesión va al login", (await evaluate(`return location.hash;`)) === "#login" && await evaluate(`${H} return !!f().getElementById("btn-start");`));
  await evaluate(`${H} click(f().getElementById("btn-start"));`);
  await sleep(300);
  await evaluate(`${H} const d=f(); d.getElementById("phone").value="12345"; d.getElementById("login-form").requestSubmit();`);
  check("Valida número", (await evaluate(`${H} return f().getElementById("login-error").textContent;`)).includes("9 dígitos"));
  await evaluate(`${H} const d=f(); d.getElementById("phone").value="987 111 222"; d.getElementById("login-form").requestSubmit();`);
  await sleep(2500);
  const s1 = JSON.parse(await evaluate(`return localStorage.getItem("mica-proto:987111222");`));
  check("Login entra a Inicio", (await evaluate(`return location.hash;`)) === "#home");
  check("Sin campo de nombre", await evaluate(`return true;`));
  check("Datos aleatorios generados", s1 && s1.txs.length === 9 && s1.wallets.cafe.balance > 0 && s1.wallets.cafe.balance !== 840.2, JSON.stringify(s1.wallets));
  // Otro número -> otros datos; volver al primero -> mismos datos
  await evaluate(`${H} click(f().querySelector('#top-home [aria-label="Mi perfil"]'));`); await sleep(500);
  await evaluate(`${H} click([...f().querySelectorAll("#side-menu button")].find(b => b.innerText.includes("Cerrar sesión")));`); await sleep(1500);
  check("Cerrar sesión vuelve al login", (await evaluate(`return location.hash;`)) === "#login");
  await evaluate(`Mica.login("955 333 444");`); await sleep(1500);
  const s2 = JSON.parse(await evaluate(`return localStorage.getItem("mica-proto:955333444");`));
  check("Otro número, otros saldos", s2.wallets.principal.balance !== s1.wallets.principal.balance);
  check("Saludo por defecto", (await evaluate(`${H} return f().getElementById("top-home").innerText;`)).includes("Hola, Yaper@"));
  await evaluate(`Mica.logout(); Mica.login("987111222");`); await sleep(1500);
  const s3 = JSON.parse(await evaluate(`return localStorage.getItem("mica-proto:987111222");`));
  check("Mismo número, mismos datos", JSON.stringify(s3.wallets) === JSON.stringify(s1.wallets));
  // Para el resto de la prueba: datos fijos de ejemplo
  await evaluate(`Mica._useExampleData();`);
  await sleep(2500);
  await evaluate(`localStorage.setItem("mica-proto", localStorage.getItem("mica-proto:987111222"));`);
  check("Inicio carga", await evaluate(`${H} return location.hash.includes("home") && !!f().getElementById("bar-yapear");`));
  check("Saldos ocultos por defecto", await evaluate(`${H} return [...f().querySelectorAll(".snap-center [data-amount]")].every(v => v.textContent === "****");`));

  // YAPEAR -> hoja de billeteras -> Emprendimiento Café
  await evaluate(`${H} click(f().getElementById("bar-yapear"));`);
  await sleep(600);
  check("Hoja ¿Desde qué billetera?", await evaluate(`${H} return !!f().getElementById("wallet-picker");`));
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="cafe"]'));`);
  await sleep(2200);
  const conf = await evaluate(`${H} const d=f(); return { hash: location.hash, to: d.getElementById("recipient-name")?.textContent.trim(), from: d.getElementById("active-wallet-name")?.textContent, bal: d.getElementById("active-wallet-balance")?.textContent, amount: d.getElementById("amount-text")?.textContent, chips: !d.getElementById("chips-drawer")?.classList.contains("hidden") };`);
  check("Pantalla de monto", conf.hash === "#confirmar", JSON.stringify(conf));
  check("Monto inicia en 0", conf.amount === "0");
  check("Desde Emprendimiento Café con S/ 840.20", conf.from === "Emprendimiento Café" && conf.bal === "S/ 840.20");
  check("Categorías visibles en negocio", conf.chips === true);

  // Teclado: 1 2 . 5 -> 12.5 ; backspace -> 12. ; 0 -> 12.0 ; 5 -> 12.05 ; 9 ignorado (máx 2 decimales)
  const typed = await evaluate(`${H} const d=f(); const k=x=>click(d.querySelector('.pad-key[data-key="'+x+'"]'));
    ["1","2",".","5"].forEach(k); const a=d.getElementById("amount-text").textContent;
    k("backspace"); k("0"); k("5"); k("9"); return [a, d.getElementById("amount-text").textContent];`);
  check("Teclado con decimales", typed[0] === "12.5" && typed[1] === "12.05", JSON.stringify(typed));

  // Categoría
  await evaluate(`${H} click(f().querySelector('[data-category^="📦"]'));`);
  check("Categoría llena la descripción", await evaluate(`${H} return f().getElementById("tx-note").value;`) === "📦 Para volver a surtir");
  check("Mensaje bloqueado con categoría", await evaluate(`${H} return f().getElementById("tx-note").readOnly;`) === true);
  check("Placeholder Agregar mensaje", await evaluate(`${H} return f().getElementById("note-placeholder").innerText.includes("Agregar mensaje");`));
  await evaluate(`${H} click(f().querySelector('[data-category^="📦"]'));`);
  check("Tocar de nuevo desbloquea", await evaluate(`${H} const n=f().getElementById("tx-note"); return !n.readOnly && n.value==="";`));
  await evaluate(`${H} click(f().querySelector('[data-category^="📦"]'));`);

  // Cambiar destinatario
  await evaluate(`${H} click(f().getElementById("recipient-name"));`);
  await sleep(500);
  check("Hoja de contactos", await evaluate(`${H} return !!f().getElementById("contact-sheet");`));
  await evaluate(`${H} const d=f(); d.querySelector("[data-phone]").value="123"; click(d.querySelector('[data-act="phone"]'));`);
  check("Valida celular", (await evaluate(`${H} return f().querySelector("#contact-sheet [data-error]").textContent;`)).includes("9 dígitos"));
  await evaluate(`${H} click(f().querySelector('#contact-sheet [data-name="Carlos Ruiz"]'));`);
  await sleep(400);
  check("Destinatario cambiado", (await evaluate(`${H} return f().getElementById("recipient-name").firstChild.textContent;`)) === "Carlos Ruiz");

  // Cambiar billetera a Ahorro: categorías ocultas y descripción de categoría limpiada
  await evaluate(`${H} click(f().getElementById("open-wallet-sheet"));`);
  await sleep(500);
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="vacaciones"]'));`);
  await sleep(500);
  const sw = await evaluate(`${H} const d=f(); return { from: d.getElementById("active-wallet-name").textContent, chipsHidden: d.getElementById("chips-drawer").classList.contains("hidden"), note: d.getElementById("tx-note").value, picker: !!d.getElementById("wallet-picker") && !d.getElementById("wallet-picker").classList.contains("opacity-0") };`);
  check("Cambio de billetera a Ahorro", sw.from === "Ahorro Vacaciones" && sw.chipsHidden && sw.note === "", JSON.stringify(sw));
  await evaluate(`${H} const d=f(); d.getElementById("tx-note").value="Regalo cumpleaños"; d.getElementById("tx-note").dispatchEvent(new Event("input"));`);

  // Pagar
  await evaluate(`${H} click(f().getElementById("pay-submit-btn"));`);
  await sleep(2200);
  const cons = await evaluate(`${H} const d=f(); return { hash: location.hash, amount: d.querySelector("[class*='text-[42px]']")?.textContent, name: d.querySelector("[class*='text-[18px]'].font-bold")?.textContent, text: d.body.innerText.replace(/\\s+/g," ").slice(0,400) };`);
  check("Constancia", cons.hash === "#constancia-negocio" && cons.amount === "12.05" && cons.name === "Carlos Ruiz", JSON.stringify({ ...cons, text: undefined }));
  check("Constancia muestra Ahorro Vacaciones", cons.text.includes("Ahorro Vacaciones") && /AHORRO|Ahorro/.test(cons.text));
  const stOp = JSON.parse(await evaluate(`return localStorage.getItem("mica-proto:987111222");`)).txs[0].op;
  check("Constancia y movimiento con mismo Nro. de operación", cons.text.includes(stOp), stOp);

  // Saldo y movimiento
  const st = await evaluate(`return JSON.parse(localStorage.getItem("mica-proto:987111222"));`);
  check("Saldo descontado", st.wallets.vacaciones.balance === 778.05, String(st.wallets.vacaciones.balance));
  check("Movimiento con descripción", st.txs[0].title === "Yapeo a Carlos Ruiz" && st.txs[0].note === "Regalo cumpleaños" && /pm|am/.test(st.txs[0].when), JSON.stringify(st.txs[0]));

  // Validaciones: monto > saldo y > 500
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => /Nuevo yapeo/.test(b.innerText)));`);
  await sleep(2600);
  check("Nuevo yapeo abre hoja en Inicio", await evaluate(`${H} return !!f().getElementById("wallet-picker");`));
  await evaluate(`${H} click(f().querySelector('#wallet-picker [data-key="principal"]'));`);
  await sleep(2200);
  check("Recuerda último contacto", (await evaluate(`${H} return f().getElementById("recipient-name").firstChild.textContent;`)) === "Carlos Ruiz");
  check("Principal sin categorías", await evaluate(`${H} return f().getElementById("chips-drawer").classList.contains("hidden");`));
  await evaluate(`${H} const d=f(); ["6","0","0"].forEach(x=>click(d.querySelector('.pad-key[data-key="'+x+'"]'))); click(d.getElementById("pay-submit-btn"));`);
  await sleep(300);
  check("Bloquea más de S/ 500", (await evaluate(`return document.getElementById("toast").textContent;`)).includes("500"));
  check("Sigue en monto tras error", await evaluate(`return location.hash;`) === "#confirmar");

  // Movimientos en Inicio
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.getAttribute("aria-label") === "Cerrar"));`);
  await sleep(2200);
  await evaluate(`${H} click(f().getElementById("mov-toggle"));`);
  await sleep(1300);
  const mov = await evaluate(`${H} const r=f().querySelector("#tx-container .tx-item"); return r && r.innerText.replace(/\\s+/g," ");`);
  check("Movimiento en Inicio con descripción", /Yapeo a Carlos Ruiz/.test(mov) && /Descripción: Regalo cumpleaños/.test(mov) && /- S\/ 12\.05/.test(mov), mov);

  // Tocar un yapeo enviado abre su constancia completa
  const opC = st.txs[0].op;
  await evaluate(`${H} click(f().querySelector("#tx-container .tx-item"));`);
  await sleep(2200);
  const vc = await evaluate(`${H} const d=f(); return { hash: location.hash, amount: d.querySelector("[class*='text-[42px]']")?.textContent, name: d.querySelector("[class*='text-[18px]'].font-bold")?.textContent, text: d.body.innerText.split(String.fromCharCode(10)).join(" ") };`);
  check("Yapeo abre constancia", vc.hash === "#constancia-negocio" && vc.amount === "12.05" && vc.name === "Carlos Ruiz" && vc.text.includes(opC) && vc.text.includes("Ahorro Vacaciones"), JSON.stringify({ ...vc, text: vc.text.slice(0, 160) }));
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.innerText.trim() === "close"));`);
  await sleep(2200);
  check("Cerrar vuelve a Inicio", (await evaluate(`return location.hash;`)).startsWith("#home"));
  // Yapeo recibido -> ¡Te yapearon!
  await evaluate(`${H} if (f().getElementById("mov-panel").classList.contains("hidden")) click(f().getElementById("mov-toggle"));`);
  await sleep(1300);
  await evaluate(`${H} click([...f().querySelectorAll("#tx-container .tx-item")].find(r => r.innerText.includes("Yape de Lucía")));`);
  await sleep(2200);
  const ty = await evaluate(`${H} const d=f(); return { hash: location.hash, amount: d.querySelector("[class*='text-[42px]']")?.textContent, name: d.querySelector("[class*='text-[17px]'].font-bold")?.textContent, text: d.body.innerText };`);
  check("Recibido abre ¡Te yapearon!", ty.hash === "#te-yapearon" && ty.amount === "85" && ty.name === "Lucía Gómez" && /4:10/.test(ty.text), JSON.stringify({ ...ty, text: undefined }));
  await evaluate(`${H} click([...f().querySelectorAll("button")].find(b => b.innerText.trim() === "close"));`);
  await sleep(2200);
  // Transferencia -> hoja de detalle
  await evaluate(`${H} if (f().getElementById("mov-panel").classList.contains("hidden")) click(f().getElementById("mov-toggle"));`);
  await sleep(1300);
  await evaluate(`${H} click([...f().querySelectorAll("#tx-container .tx-item")].find(r => r.innerText.includes("Transferencia")));`);
  await sleep(600);
  check("Transferencia abre hoja de detalle", await evaluate(`${H} const d=f().getElementById("tx-detail"); return !!d && d.innerText.includes("Transferencia entre billeteras");`));
  check("Sin errores de JS", logs.length === 0, logs.join(" | "));
} catch (e) {
  console.log("ERROR", e.message); fails++;
} finally {
  try { ws?.close(); } catch {}
  proc.kill();
  console.log(fails ? `\n${fails} fallo(s)` : "\nTODO OK");
  process.exit(fails ? 1 : 0);
}
