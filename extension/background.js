chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ping") {
    console.log("[manga-jisho] ping from", sender.tab?.url);
    sendResponse("pong");
  }
});
