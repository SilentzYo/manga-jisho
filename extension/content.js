console.log("[manga-jisho] loaded on", location.href);

chrome.runtime.sendMessage({ type: "ping" }, reply => {
  console.log("[manga-jisho] background says", reply);
});
