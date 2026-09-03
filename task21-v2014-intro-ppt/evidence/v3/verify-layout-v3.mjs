const endpoint = process.argv[2] || "http://127.0.0.1:9223/json";
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
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

function call(method, params = {}) {
  const id = ++requestId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

await call("Emulation.setDeviceMetricsOverride", {
  width: 1600,
  height: 900,
  deviceScaleFactor: 1,
  mobile: false
});
await call("Page.reload", { ignoreCache: true });
await call("Runtime.evaluate", {
  expression: "new Promise(resolve => setTimeout(() => requestAnimationFrame(() => requestAnimationFrame(resolve)), 250))",
  awaitPromise: true
});

const expression = `(() => {
  const slide = document.getElementById('slide');
  const visible = (node) => {
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const label = (node) => node.className || node.id || node.tagName;
  const all = [...slide.querySelectorAll('*')].filter(visible);
  const overflowTargets = all.filter((node) => node.matches('.topline,.evolution,.matrix,.cell,.domain-graphic,.domain-grid,.icon-flow,.icon-step,.value-visual,.stairs,.insight-flow,.insight,.bottom,.data-panel,.compare-list,.compare-row,.entity,.role-panel,.role-map,.role-node,.role-hub,.era,.row-label'));
  const overflow = overflowTargets.filter((node) => node.scrollWidth > node.clientWidth + 3 || node.scrollHeight > node.clientHeight + 3)
    .map((node) => ({ node: label(node), client: [node.clientWidth, node.clientHeight], scroll: [node.scrollWidth, node.scrollHeight] }));
  const slideRect = slide.getBoundingClientRect();
  const outOfBounds = all.filter((node) => {
    const r = node.getBoundingClientRect();
    return r.left < slideRect.left - 1 || r.top < slideRect.top - 1 || r.right > slideRect.right + 1 || r.bottom > slideRect.bottom + 1;
  }).map((node) => label(node));
  const groups = ['.topline', '.evolution', '.matrix', '.bottom', '.domain-grid', '.icon-flow', '.value-visual', '.stairs', '.insight-flow', '.compare-list', '.compare-row', '.entity'];
  const overlaps = [];
  for (const selector of groups) {
    const parent = slide.querySelector(selector);
    if (!parent) continue;
    const children = [...parent.children].filter(visible);
    for (let i = 0; i < children.length; i++) {
      for (let j = i + 1; j < children.length; j++) {
        const a = children[i].getBoundingClientRect();
        const b = children[j].getBoundingClientRect();
        const width = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const height = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        if (width > 1 && height > 1) overlaps.push({ group: selector, a: label(children[i]), b: label(children[j]), area: Math.round(width * height) });
      }
    }
  }
  return {
    viewport: [innerWidth, innerHeight],
    slide: [Math.round(slideRect.width), Math.round(slideRect.height)],
    overflow,
    outOfBounds,
    overlaps,
    titleLines: Math.round(slide.querySelector('h1').getBoundingClientRect().height / parseFloat(getComputedStyle(slide.querySelector('h1')).lineHeight))
  };
})()`;

const evaluated = await call("Runtime.evaluate", { expression, returnByValue: true });
const report = evaluated.result.value;
console.log(JSON.stringify(report, null, 2));
socket.close();

if (report.overflow.length || report.outOfBounds.length || report.overlaps.length || report.titleLines !== 1) {
  process.exitCode = 1;
}
