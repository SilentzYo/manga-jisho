console.log("[manga-jisho] loaded on", location.href);

chrome.runtime.sendMessage({ type: "ping" }, reply => {
  console.log("[manga-jisho] background says", reply);
});

const MIN_WIDTH = 300;
const MIN_HEIGHT = 400;
const pages = new WeakMap();

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

new MutationObserver(scanSoon).observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src", "srcset"],
});
document.addEventListener("load", scanSoon, true);
addEventListener("resize", scanSoon);
scan();
