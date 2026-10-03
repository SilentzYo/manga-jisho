const MIN_WIDTH = 300;
const MIN_HEIGHT = 400;
const MAX_SENSES = 4;
const pages = new WeakMap();
const results = new Map();
const lookups = new Map();
const mouse = { x: 0, y: 0 };
let wanted = null;
let shownWord = null;

const overlay = create("div", "manga-jisho-overlay");
const blockMark = create("div", "manga-jisho-block");
const wordMarks = create("div");
const popup = create("div", "manga-jisho-popup");
overlay.append(blockMark, wordMarks, popup);
document.documentElement.append(overlay);

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function sourceOf(element) {
  return element.tagName === "IMG" ? element.currentSrc || element.src : "canvas";
}

function scan() {
  for (const element of document.querySelectorAll("img, canvas")) {
    const { width, height } = element.getBoundingClientRect();
    const isPage = width >= MIN_WIDTH && height >= MIN_HEIGHT;
    element.classList.toggle("manga-jisho-page", isPage);

    const source = sourceOf(element);
    if (isPage && pages.get(element) !== source) {
      pages.set(element, source);
      console.log("[manga-jisho] page", Math.round(width), "x", Math.round(height), source);
    }
  }
}

let timer;
function scanSoon() {
  clearTimeout(timer);
  timer = setTimeout(scan, 200);
}

function contains([x1, y1, x2, y2], x, y) {
  return x >= x1 && x <= x2 && y >= y1 && y <= y2;
}

function distance([x1, y1, x2, y2], x, y) {
  return Math.hypot(Math.max(x1 - x, 0, x - x2), Math.max(y1 - y, 0, y - y2));
}

function pageAt(x, y) {
  return [...document.querySelectorAll(".manga-jisho-page")].find(page => {
    const { left, top, right, bottom } = page.getBoundingClientRect();
    return contains([left, top, right, bottom], x, y);
  });
}

async function readPage(page) {
  const source = page.tagName === "IMG" ? sourceOf(page) : page.toDataURL("image/jpeg");
  const result = await chrome.runtime.sendMessage({ type: "ocr", source, referrer: location.href });
  if (result.error) throw new Error(result.error);
  return result;
}

function resultFor(page) {
  const key = page.tagName === "IMG" ? sourceOf(page) : page;
  if (results.has(key)) return results.get(key);

  results.set(key, null);
  page.classList.add("manga-jisho-reading");
  const started = performance.now();
  readPage(page)
    .then(result => {
      results.set(key, result);
      const seconds = ((performance.now() - started) / 1000).toFixed(1);
      console.log("[manga-jisho]", result.blocks.length, "blocks in", seconds, "s", result.blocks);
      update();
    })
    .catch(error => console.warn("[manga-jisho]", error.message))
    .finally(() => page.classList.remove("manga-jisho-reading"));
  return null;
}

function lookUp(text, at) {
  const key = `${at}:${text}`;
  if (lookups.has(key)) return lookups.get(key);

  lookups.set(key, undefined);
  chrome.runtime.sendMessage({ type: "lookup", text, at })
    .then(word => {
      if (word?.error) throw new Error(word.error);
      lookups.set(key, word);
      if (wanted === key) update();
    })
    .catch(error => console.warn("[manga-jisho]", error.message));
  return undefined;
}

function characterAt(block, x, y) {
  if (!block.lines.length) return null;
  const line = block.lines.reduce((best, line) =>
    distance(line.box, x, y) < distance(best.box, x, y) ? line : best);

  const [x1, y1, x2, y2] = line.box;
  const along = block.vertical ? (y - y1) / (y2 - y1) : (x - x1) / (x2 - x1);
  return line.start + Math.floor(Math.min(Math.max(along, 0), 0.999) * line.text.length);
}

function segments(block, start, end) {
  return block.lines
    .filter(line => line.start < end && line.start + line.text.length > start)
    .map(line => {
      const [x1, y1, x2, y2] = line.box;
      const length = line.text.length;
      const from = (Math.max(start, line.start) - line.start) / length;
      const to = (Math.min(end, line.start + length) - line.start) / length;
      return block.vertical
        ? [x1, y1 + from * (y2 - y1), x2, y1 + to * (y2 - y1)]
        : [x1 + from * (x2 - x1), y1, x1 + to * (x2 - x1), y2];
    });
}

function place(mark, box, scale, [x1, y1, x2, y2]) {
  Object.assign(mark.style, {
    display: "block",
    left: `${box.left + x1 * scale.x}px`,
    top: `${box.top + y1 * scale.y}px`,
    width: `${(x2 - x1) * scale.x}px`,
    height: `${(y2 - y1) * scale.y}px`,
  });
}

function render(word) {
  popup.replaceChildren();
  if (!word.entries.length) {
    popup.append(create("div", "manga-jisho-missing", `${word.word}: not in the dictionary`));
  }
  for (const entry of word.entries) {
    const head = create("div", "manga-jisho-head");
    head.append(create("span", "manga-jisho-written", entry.kanji[0] ?? entry.kana[0] ?? word.word));
    if (entry.kanji.length && entry.kana.length) {
      head.append(create("span", "manga-jisho-reading", entry.kana[0]));
    }

    const senses = create("ol", "manga-jisho-senses");
    for (const sense of entry.senses.slice(0, MAX_SENSES)) {
      const item = create("li");
      item.append(create("span", "manga-jisho-pos", sense.pos.join(", ")), sense.glosses.join("; "));
      senses.append(item);
    }
    popup.append(head, senses);
  }
}

function showPopup() {
  popup.style.display = "block";
  const { width, height } = popup.getBoundingClientRect();
  let left = mouse.x + 16;
  let top = mouse.y + 16;
  if (left + width > innerWidth - 8) left = mouse.x - width - 16;
  if (top + height > innerHeight - 8) top = innerHeight - height - 8;
  popup.style.left = `${Math.max(8, left)}px`;
  popup.style.top = `${Math.max(8, top)}px`;
}

function hideWord() {
  wordMarks.replaceChildren();
  popup.style.display = "none";
  shownWord = null;
}

function showWord(block, box, scale, word) {
  wordMarks.replaceChildren(...segments(block, word.start, word.end).map(segment => {
    const mark = create("div", "manga-jisho-word");
    place(mark, box, scale, segment);
    return mark;
  }));

  const id = `${word.start}:${word.end}:${block.text}`;
  if (id === shownWord) return;
  shownWord = id;
  render(word);
  showPopup();
}

function hovered() {
  const page = pageAt(mouse.x, mouse.y);
  const result = page && resultFor(page);
  if (!result) return null;

  const box = page.getBoundingClientRect();
  const scale = { x: box.width / result.width, y: box.height / result.height };
  const x = (mouse.x - box.left) / scale.x;
  const y = (mouse.y - box.top) / scale.y;
  const block = result.blocks.find(block => contains(block.box, x, y));
  const at = block && characterAt(block, x, y);
  return at == null ? null : { block, box, scale, at };
}

function update() {
  const target = hovered();
  if (!target) {
    blockMark.style.display = "none";
    wanted = null;
    hideWord();
    return;
  }

  const { block, box, scale, at } = target;
  place(blockMark, box, scale, block.box);
  wanted = `${at}:${block.text}`;
  const word = lookUp(block.text, at);
  if (word === null) hideWord();
  if (word) showWord(block, box, scale, word);
}

addEventListener("mousemove", event => {
  mouse.x = event.clientX;
  mouse.y = event.clientY;
  update();
}, { passive: true });

addEventListener("scroll", update, { capture: true, passive: true });

new MutationObserver(records => {
  if (records.some(record => !overlay.contains(record.target))) scanSoon();
}).observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src", "srcset"],
});
document.addEventListener("load", scanSoon, true);
addEventListener("resize", scanSoon);
scan();
