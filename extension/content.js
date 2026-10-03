const MIN_WIDTH = 300;
const MIN_HEIGHT = 400;
const pages = new WeakMap();
const mouse = { x: 0, y: 0 };

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

function pageAt(x, y) {
  return [...document.querySelectorAll(".manga-jisho-page")].find(page => {
    const box = page.getBoundingClientRect();
    return x >= box.left && x <= box.right && y >= box.top && y <= box.bottom;
  });
}

async function readPage(page) {
  const source = page.tagName === "IMG" ? sourceOf(page) : page.toDataURL("image/jpeg");
  console.log("[manga-jisho] reading", sourceOf(page));

  const started = performance.now();
  const result = await chrome.runtime.sendMessage({ type: "ocr", source, referrer: location.href });
  const seconds = ((performance.now() - started) / 1000).toFixed(1);

  if (result.error) {
    console.warn("[manga-jisho]", result.error);
  } else {
    console.log("[manga-jisho]", result.blocks.length, "blocks in", seconds, "s", result.blocks);
  }
}

addEventListener("mousemove", event => {
  mouse.x = event.clientX;
  mouse.y = event.clientY;
}, { passive: true });

addEventListener("keydown", event => {
  if (!event.altKey || event.code !== "KeyO") return;
  const page = pageAt(mouse.x, mouse.y);
  if (!page) {
    console.log("[manga-jisho] no page under the mouse");
    return;
  }
  event.preventDefault();
  readPage(page).catch(error => console.warn("[manga-jisho]", error.message));
});

new MutationObserver(scanSoon).observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src", "srcset"],
});
document.addEventListener("load", scanSoon, true);
addEventListener("resize", scanSoon);
scan();
