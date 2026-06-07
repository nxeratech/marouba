import "./style.css";
import { invoke } from "@tauri-apps/api/core";

type RecordedEvent = {
  kind: string;
  timestamp_ms: number;
  x?: number;
  y?: number;
  button?: string;
  key?: string;
  window_title?: string;
  element_name?: string;
};

type RecordingStatus = {
  mode: string;
  active_window: { title: string; app_name: string };
  steps: RecordedEvent[];
  last_actions: string[];
};

const mode = document.querySelector<HTMLParagraphElement>("#mode")!;
const dot = document.querySelector<HTMLSpanElement>("#dot")!;
const windowLabel = document.querySelector<HTMLHeadingElement>("#window")!;
const actions = document.querySelector<HTMLOListElement>("#actions")!;
const steps = document.querySelector<HTMLDivElement>("#steps")!;
const review = document.querySelector<HTMLElement>("#review")!;
const workflowName = document.querySelector<HTMLInputElement>("#workflow-name")!;
const saveButton = document.querySelector<HTMLButtonElement>("#save")!;
const message = document.querySelector<HTMLParagraphElement>("#message")!;
const recordButton = document.querySelector<HTMLButtonElement>("#record")!;
const stopButton = document.querySelector<HTMLButtonElement>("#stop")!;
let savedStatus: string | null = null;

recordButton.addEventListener("click", async () => {
  savedStatus = null;
  message.textContent = "";
  await invoke("start_recording");
  await refresh();
});

stopButton.addEventListener("click", async () => {
  message.textContent = "";
  await invoke("stop_recording");
  await refresh();
});

document.querySelector<HTMLButtonElement>("#open-vault")!.addEventListener("click", async () => {
  await invoke("open_vault");
});

saveButton.addEventListener("click", async () => {
  const keepIndexes = Array.from(steps.querySelectorAll<HTMLInputElement>("input[data-index]"))
    .filter((input) => input.checked)
    .map((input) => Number(input.dataset.index));
  const name = workflowName.value.trim() || "Tray Recorded Workflow";
  saveButton.disabled = true;
  message.textContent = "Saving workflow...";
  try {
    const path = await invoke<string>("save_workflow", {
      request: { name, keep_indexes: keepIndexes },
    });
    savedStatus = `Saved: ${name}`;
    message.textContent = path;
    await refresh();
  } catch (error) {
    message.textContent = String(error);
  } finally {
    saveButton.disabled = false;
  }
});

async function refresh() {
  try {
    const status = await invoke<RecordingStatus>("recording_status");
    render(status);
  } catch (error) {
    mode.textContent = "offline";
    dot.classList.remove("recording");
    windowLabel.textContent = "Companion unavailable";
    message.textContent = String(error);
  }
}

function render(status: RecordingStatus) {
  const isRecording = status.mode === "recording";
  mode.textContent = savedStatus ?? (isRecording ? "Recording..." : "Idle");
  dot.classList.toggle("recording", status.mode === "recording");
  recordButton.disabled = isRecording;
  stopButton.disabled = !isRecording;
  windowLabel.textContent = `${status.active_window.app_name || "unknown"} - ${status.active_window.title || "unknown window"}`;

  actions.replaceChildren(
    ...status.last_actions.map((label) => {
      const item = document.createElement("li");
      item.textContent = label;
      return item;
    }),
  );

  review.hidden = status.steps.length === 0 || status.mode === "recording";
  steps.replaceChildren(
    ...status.steps.map((step, index) => {
      const row = document.createElement("label");
      row.className = "step";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.dataset.index = String(index);

      const text = document.createElement("span");
      text.textContent = describeStep(step, index);

      row.append(checkbox, text);
      return row;
    }),
  );
}

function describeStep(step: RecordedEvent, index: number) {
  if (step.kind === "mousemove") {
    return `${index + 1}. move (${step.x}, ${step.y})`;
  }
  if (step.kind === "mousedown" || step.kind === "mouseup") {
    const element = step.element_name ? ` on ${step.element_name}` : "";
    return `${index + 1}. ${step.kind} ${step.button ?? "left"} (${step.x}, ${step.y})${element}`;
  }
  if (step.kind === "keydown" || step.kind === "keyup") {
    return `${index + 1}. ${step.kind} ${step.key}`;
  }
  if (step.kind === "focus") {
    return `${index + 1}. focus ${step.window_title ?? "unknown window"}`;
  }
  return `${index + 1}. ${step.kind}`;
}

refresh();
setInterval(refresh, 1500);
