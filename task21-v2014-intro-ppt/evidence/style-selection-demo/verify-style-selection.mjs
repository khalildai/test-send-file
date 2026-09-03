import { writeFileSync } from "node:fs";

const endpoint = process.argv[2] || "http://127.0.0.1:9224/json";
const width = Number(process.argv[3] || 1600);
const height = Number(process.argv[4] || 1200);
const screenshotPath = process.argv[5];
const pages = await (await fetch(endpoint)).json();
const page = pages.find((item) => item.type === "page");
if (!page) throw new Error("No Chrome page target found");

const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});
let requestId = 0;
const pending = new Map();
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const handlers = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) handlers.reject(new Error(message.error.message));
  else handlers.resolve(message.result);
});
function call(method, params = {}) {
  const id = ++requestId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}
await call("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: width < 600 });
await call("Page.reload", { ignoreCache: true });
await call("Runtime.evaluate", { expression: "new Promise(r=>setTimeout(()=>requestAnimationFrame(()=>requestAnimationFrame(r)),250))", awaitPromise: true });
const expression = `(() => {
  const root = document.querySelector('.page');
  const visible = n => { const s=getComputedStyle(n),r=n.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0; };
  const checked = [...document.querySelectorAll('.header,.note,.section,.options,.option,.option-body,.levels-a,.lanes,.portfolio,.insight-grid,.insight,.charts,.chart-card,.chart,.bar-area,.decision,.footer')].filter(visible);
  const overflow = checked.filter(n=>n.scrollWidth>n.clientWidth+3||n.scrollHeight>n.clientHeight+3).map(n=>({node:n.className,client:[n.clientWidth,n.clientHeight],scroll:[n.scrollWidth,n.scrollHeight]}));
  const external = [...document.querySelectorAll('[src],[href]')].map(n=>n.src||n.href).filter(v=>/^https?:/i.test(v));
  document.querySelector('[data-group="goal"][data-choice="B"] .select').click();
  document.querySelector('[data-group="dept"][data-choice="C"] .select').click();
  const saved = JSON.parse(localStorage.getItem('task21-style-selection-demo')||'{}');
  return {viewport:[innerWidth,innerHeight],page:[root.scrollWidth,root.scrollHeight],body:[document.body.scrollWidth,document.body.scrollHeight],cards:document.querySelectorAll('[data-group]').length,overflow,external,saved};
})()`;
const evaluated = await call("Runtime.evaluate", { expression, returnByValue: true });
const report = evaluated.result.value;
console.log(JSON.stringify(report, null, 2));
if (screenshotPath) {
  const shot = await call("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
  writeFileSync(screenshotPath, Buffer.from(shot.data, "base64"));
}
socket.close();
if (report.cards !== 6 || report.overflow.length || report.external.length || report.saved.goal !== "B" || report.saved.dept !== "C") process.exitCode = 1;
