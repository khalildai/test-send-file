const endpoint = process.argv[2] || "http://127.0.0.1:9228/json";
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
await call("Emulation.setDeviceMetricsOverride", { width: viewportWidth, height: viewportHeight, deviceScaleFactor: 1, mobile: false });
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
  const overflowTargets = all.filter((node) => node.matches('.topline,.era,.special,.roles,.role,.matrix,.cell,.three,.module,.design-new,.owner-box,.domains,.domain-grid,.domain,.compare-box,.op,.value-old,.value-new,.goal-box,.steps,.outcomes,.outcome,.example,.example-grid,.panel,.radar-wrap,.radar,.diag-list,.diag-item,.dept-chart,.plot,.bars,.bar,.analysis-line,.domain-bars,.domain-row,.pair,.trend,.advice,.advice-row,.risk'));
  const overflow = overflowTargets.filter((node) => node.scrollWidth > node.clientWidth + 3 || node.scrollHeight > node.clientHeight + 3)
    .map((node) => ({ node: label(node), client: [node.clientWidth, node.clientHeight], scroll: [node.scrollWidth, node.scrollHeight] }));
  const slideRect = slide.getBoundingClientRect();
  const outOfBounds = all.filter((node) => {
    const rect = node.getBoundingClientRect();
    return rect.left < slideRect.left - 1 || rect.top < slideRect.top - 1 || rect.right > slideRect.right + 1 || rect.bottom > slideRect.bottom + 1;
  }).map((node) => label(node));
  const groups = ['.topline','.era','.special','.roles','.matrix','.three','.design-new','.domain-grid','.value-old','.value-new','.steps','.outcomes','.example-grid','.radar-wrap','.diag-list','.bars','.domain-bars','.domain-row','.analysis-line','.advice','.risk'];
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
  const columns = getComputedStyle(slide.querySelector('.matrix')).gridTemplateColumns.split(' ').map(parseFloat);
  const req = {
    comparisonRatio: Number((columns[1] / columns[2]).toFixed(3)),
    exampleHeight: slide.querySelector('.example').clientHeight,
    sixDomains: slide.querySelectorAll('.domain').length,
    oldOperationIcons: slide.querySelectorAll('.oldop svg').length,
    analysisLabels: [...slide.querySelectorAll('.analysis-line b')].filter((node) => node.textContent.includes('现状分析')).length,
    riskLabels: [...slide.querySelectorAll('.risk b')].filter((node) => node.textContent.includes('年度目标达成风险评估')).length,
    removedExampleSubtitle: !text.includes('演示数据 · 当前 9 月 · 各视角独立呈现'),
    hasProgressWording: text.includes('偏重进度管理') && !text.includes('偏重协助算分'),
    preservedViews: ['科组视角','部门视角','业务视角','改进建议','运控测试组','驱动测试部','伺服产品业务'].every((item) => text.includes(item))
  };
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
    requirements: req
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
const req = report.requirements;
const requirementsOk = req.comparisonRatio >= 0.667 && req.comparisonRatio <= 0.8 && req.exampleHeight >= 290 && req.sixDomains === 6 && req.oldOperationIcons === 3 && req.analysisLabels === 2 && req.riskLabels === 1 && req.removedExampleSubtitle && req.hasProgressWording && req.preservedViews;
if (report.overflow.length || report.outOfBounds.length || report.overlaps.length || report.titleLines !== 1 || report.externalResources !== 0 || !requirementsOk) process.exitCode = 1;
