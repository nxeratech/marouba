import "./style.css";

const mode = document.querySelector<HTMLParagraphElement>("#mode")!;
const windowLabel = document.querySelector<HTMLHeadingElement>("#window")!;
const actions = document.querySelector<HTMLOListElement>("#actions")!;

async function refreshWindow() {
  try {
    const response = await fetch("http://127.0.0.1:7842/window");
    const data = await response.json();
    mode.textContent = "idle";
    windowLabel.textContent = `${data.app_name ?? "unknown"} - ${data.title ?? "unknown window"}`;
  } catch {
    mode.textContent = "offline";
    windowLabel.textContent = "Companion API unavailable";
  }
}

function addAction(label: string) {
  const item = document.createElement("li");
  item.textContent = label;
  actions.prepend(item);
  while (actions.children.length > 5) {
    actions.lastElementChild?.remove();
  }
}

addAction("Mac companion started");
refreshWindow();
setInterval(refreshWindow, 1500);
