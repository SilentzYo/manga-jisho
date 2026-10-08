const sentence = document.querySelector("#sentence");
const jisho = document.querySelector("#jisho");
const entries = document.querySelector("#entries");
const form = document.querySelector("#settings");
const notice = document.querySelector("#notice");
let windowId;
let noticeTimer;

chrome.windows.getCurrent().then(current => windowId = current.id);

chrome.storage.local.get(DEFAULT_SETTINGS).then(saved => {
  for (const [name, value] of Object.entries(saved)) {
    const field = form.elements[name];
    if (field?.type === "checkbox") field.checked = value;
    else if (field) field.value = value;
  }
});

document.addEventListener("change", () => {
  const readAhead = Math.min(10, Math.max(0, Math.round(Number(form.elements.readAhead.value)) || 0));
  form.elements.readAhead.value = readAhead;
  chrome.storage.local.set({
    translate: form.elements.translate.checked,
    deeplKey: form.elements.deeplKey.value.trim(),
    model: form.elements.model.value,
    readAhead,
    borders: form.elements.borders.checked,
  });
});

chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.tab && sender.tab.windowId !== windowId) return;
  if (message.type === "word") show(message.word, message.sentence);
  if (message.type === "notice") showNotice(message.text);
});

document.querySelector("#restart").addEventListener("click", async event => {
  event.target.disabled = true;
  const reply = await chrome.runtime.sendMessage({ type: "restart" }).catch(error => ({ error: error.message }));
  if (reply?.error) showNotice(reply.error);
  event.target.disabled = false;
});

function showNotice(text) {
  notice.textContent = text;
  notice.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => notice.hidden = true, 10000);
}

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function entryView(entry, word) {
  const view = create("article", "entry");
  const head = create("h2");
  head.append(create("span", "written", entry.kanji[0] ?? entry.kana[0] ?? word));
  if (entry.kanji.length && entry.kana.length) {
    head.append(create("span", "reading", entry.kana[0]));
  }
  view.append(head);

  const others = [...entry.kanji.slice(1), ...entry.kana.slice(1)];
  if (others.length) {
    view.append(create("p", "others", `Also ${others.join("、")}`));
  }

  const senses = create("ol");
  for (const sense of entry.senses) {
    const item = create("li");
    if (sense.pos.length) item.append(create("span", "pos", sense.pos.join(", ")));
    item.append(sense.glosses.join("; "));
    senses.append(item);
  }
  view.append(senses);
  return view;
}

function show(word, text) {
  sentence.classList.remove("hint");
  sentence.replaceChildren(
    text.slice(0, word.start),
    create("mark", null, text.slice(word.start, word.end)),
    text.slice(word.end),
  );

  jisho.hidden = false;
  jisho.href = `https://jisho.org/search/${encodeURIComponent(word.word)}`;
  jisho.textContent = `Search ${word.word} on Jisho`;

  entries.replaceChildren(...word.entries.map(entry => entryView(entry, word.word)));
  if (!word.entries.length) {
    entries.append(create("p", "hint", `${word.word} isn't in the dictionary.`));
  }
  entries.scrollTop = 0;
}
