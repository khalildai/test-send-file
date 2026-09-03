const endpoint = process.argv[2] || "http://127.0.0.1:9226/json";
const viewportWidth = Number(process.argv[3] || 1600);
const viewportHeight = Number(process.argv[4] || 900);
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
  const callbacks = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) callbacks.reject(new Error(message.error.message));
  else callbacks.resolve(message.result);
});

function call(method, params = {}) {
  const id = ++requestId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

await call("Emulation.setDeviceMetricsOverride", {
  width: viewportWidth,
  height: viewportHeight,
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
  const label = (node) => String(node.className || node.id || node.tagName);
  const all = [...slide.querySelectorAll('*')].filter(visible);
  const overflowTargets = all.filter((node) => node.matches('.topline,.era,.matrix,.cell,.module-row,.domain-row,.domain,.ops-row,.op,.value-row,.goal-box,.steps,.outcomes,.outcome,.special,.roles,.role,.example,.example-grid,.panel,.radar-wrap,.radar,.diag-list,.diag-item,.dept-chart,.plot,.bars,.bar,.level-chart,.groups,.group,.actions,.action'));
  const overflow = overflowTargets.filter((node) => node.scrollWidth > node.clientWidth + 3 || node.scrollHeight > node.clientHeight + 3)
    .map((node) => ({ node: label(node), client: [node.clientWidth, node.clientHeight], scroll: [node.scrollWidth, node.scrollHeight] }));
  const slideRect = slide.getBoundingClientRect();
  const outOfBounds = all.filter((node) => {
    const rect = node.getBoundingClientRect();
    return rect.left < slideRect.left - 1 || rect.top < slideRect.top - 1 || rect.right > slideRect.right + 1 || rect.bottom > slideRect.bottom + 1;
  }).map((node) => label(node));
  const groups = ['.topline','.era','.matrix','.module-row','.domain-row','.ops-row','.value-row','.steps','.outcomes','.special','.roles','.example-grid','.radar-wrap','.diag-list','.bars','.groups','.actions'];
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
  const text = slide.innerText;
  return {
    viewport: [innerWidth, innerHeight],
    slide: [Math.round(slideRect.width), Math.round(slideRect.height)],
    overflow,
    outOfBounds,
    overlaps,
    titleLines: Math.round(slide.querySelector('h1').getBoundingClientRect().height / (parseFloat(getComputedStyle(slide.querySelector('h1')).lineHeight) * slideRect.width / 1600)),
    externalResources: [...document.querySelectorAll('[src],[href]')].filter((node) => {
      const value = node.src || node.href || '';
      return value.startsWith('http://') || value.startsWith('https://') || value.startsWith('//');
    }).length,
    requirements: {
      sixDomains: slide.querySelectorAll('.domain').length,
      threeRoles: slide.querySelectorAll('.role').length,
      departmentBars: slide.querySelectorAll('.dept-chart .bar').length,
      comparisonGroups: slide.querySelectorAll('.level-chart .group').length,
      actionTypes: slide.querySelectorAll('.action').length,
      hasUniformTarget: text.includes('涉域科组') && text.includes('同目标 3.0'),
      hasSpecialValue: text.includes('专项价值') && text.includes('SP/BP'),
      hasYearlyGoalSet: text.includes('完整测试能力年度目标合集') && text.includes('递进能力阶')
    }
  };
})()`;

const evaluated = await call("Runtime.evaluate", { expression, returnByValue: true });
const report = evaluated.result.value;
if (!report) {
  console.error(JSON.stringify(evaluated, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
socket.close();

const requirementsOk = report.requirements.sixDomains === 6 && report.requirements.threeRoles === 3 && report.requirements.departmentBars === 3 && report.requirements.comparisonGroups === 3 && report.requirements.actionTypes === 3 && report.requirements.hasUniformTarget && report.requirements.hasSpecialValue && report.requirements.hasYearlyGoalSet;
if (report.overflow.length || report.outOfBounds.length || report.overlaps.length || report.titleLines !== 1 || report.externalResources !== 0 || !requirementsOk) process.exitCode = 1;
