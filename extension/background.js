const SERVER = "http://localhost:7331";

chrome.runtime.onMessage.addListener((message, _, sendResponse) => {
  if (message.type === "ocr") {
    ocr(message.source, message.referrer).then(sendResponse, error => sendResponse({ error: error.message }));
    return true;
  }
});

async function download(source, referrer) {
  if (source.startsWith("data:")) return fetch(source);

  await chrome.declarativeNetRequest.updateSessionRules({
    removeRuleIds: [1],
    addRules: [{
      id: 1,
      condition: {
        requestDomains: [new URL(source).hostname],
        initiatorDomains: [chrome.runtime.id],
        resourceTypes: ["xmlhttprequest"],
      },
      action: {
        type: "modifyHeaders",
        requestHeaders: [
          { header: "referer", operation: "set", value: referrer },
          { header: "origin", operation: "remove" },
        ],
      },
    }],
  });
  return fetch(source, { credentials: "include" });
}

async function ocr(source, referrer) {
  const image = await download(source, referrer);
  if (!image.ok) throw new Error(`Couldn't download the page (HTTP ${image.status})`);

  const form = new FormData();
  form.append("image", await image.blob(), "page");

  const response = await fetch(`${SERVER}/ocr`, { method: "POST", body: form }).catch(() => {
    throw new Error("Can't reach the OCR server, is it running?");
  });
  if (!response.ok) throw new Error(`OCR server error (HTTP ${response.status})`);
  return response.json();
}
