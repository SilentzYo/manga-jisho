const SERVER = "http://localhost:7331";
const LAUNCHER = "com.manga_jisho.server";
const START_TIMEOUT = 90_000;
let starting = null;

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(console.error);

const handlers = {
  ocr: message => ocr(message),
  lookup: message => lookUp(message.text, message.at),
  restart: () => restart(),
};

chrome.runtime.onMessage.addListener((message, _, sendResponse) => {
  const handler = handlers[message.type];
  if (!handler) return;
  handler(message).then(sendResponse, error => sendResponse({ error: error.message }));
  return true;
});

function announce(text) {
  chrome.runtime.sendMessage({ type: "notice", text }).catch(() => {});
}

function wait(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function healthy() {
  return fetch(`${SERVER}/health`).then(response => response.ok, () => false);
}

async function launch() {
  announce("Starting the server…");
  await chrome.runtime.sendNativeMessage(LAUNCHER, { command: "start" }).catch(error => {
    throw new Error(`Can't reach the server and couldn't start it (${error.message})`);
  });
  for (const deadline = Date.now() + START_TIMEOUT; Date.now() < deadline; await wait(1000)) {
    if (await healthy()) {
      announce("The server is ready");
      return;
    }
  }
  throw new Error("The server didn't start, see server/data/server.log");
}

function startServer() {
  starting ??= launch().finally(() => starting = null);
  return starting;
}

async function restart() {
  await fetch(`${SERVER}/shutdown`, { method: "POST" }).catch(() => null);
  for (let tries = 0; tries < 30 && await healthy(); tries++) await wait(1000);
  await startServer();
  return { status: "ready" };
}

async function server(path, options) {
  let response = await fetch(`${SERVER}${path}`, options).catch(() => null);
  if (!response) {
    await startServer();
    response = await fetch(`${SERVER}${path}`, options).catch(() => null);
  }
  if (!response) throw new Error("Can't reach the server");
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
  return fetch(source, { credentials: "include" }).catch(() => {
    throw new Error("Couldn't download the page, the site or another extension blocked it");
  });
}

async function ocr({ source, referrer, model, translate, key }) {
  const image = await download(source, referrer);
  if (!image.ok) throw new Error(`Couldn't download the page (HTTP ${image.status})`);

  const form = new FormData();
  form.append("image", await image.blob(), "page");
  if (translate) form.append("translate", "true");
  if (key) form.append("key", key);
  return server(`/ocr?${new URLSearchParams({ model })}`, { method: "POST", body: form });
}

function lookUp(text, at) {
  return server(`/lookup?${new URLSearchParams({ text, at })}`);
}
