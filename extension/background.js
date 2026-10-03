const SERVER = "http://localhost:7331";

const handlers = {
  ocr: message => ocr(message.source, message.referrer),
  lookup: message => lookUp(message.text, message.at),
};

chrome.runtime.onMessage.addListener((message, _, sendResponse) => {
  const handler = handlers[message.type];
  if (!handler) return;
  handler(message).then(sendResponse, error => sendResponse({ error: error.message }));
  return true;
});

async function server(path, options) {
  const response = await fetch(`${SERVER}${path}`, options).catch(() => {
    throw new Error("Can't reach the server, is it running?");
  });
  if (!response.ok) throw new Error(`Server error (HTTP ${response.status})`);
  return response.json();
}

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
  return server("/ocr", { method: "POST", body: form });
}

function lookUp(text, at) {
  return server(`/lookup?${new URLSearchParams({ text, at })}`);
}
