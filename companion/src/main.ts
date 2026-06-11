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
  ableton_bridge?: AbletonBridgeHealth;
};

type AbletonBridgeHealth = {
  status: string;
  message?: string;
  send_port: number;
  recv_port: number;
  health_port: number;
};

type VaultWorkflow = {
  name: string;
  size_kb: number;
  modified: string;
};

const mode = document.querySelector<HTMLParagraphElement>("#mode")!;
const dot = document.querySelector<HTMLSpanElement>("#dot")!;
const windowLabel = document.querySelector<HTMLHeadingElement>("#window")!;
const actions = document.querySelector<HTMLOListElement>("#actions")!;
const workflowList = document.querySelector<HTMLDivElement>("#workflow-list")!;
const workflowActions = document.querySelector<HTMLElement>("#workflow-actions")!;
const refreshWorkflowsButton = document.querySelector<HTMLButtonElement>("#refresh-workflows")!;
const vaultDrawer = document.querySelector<HTMLElement>("#vault-drawer")!;
const closeVaultButton = document.querySelector<HTMLButtonElement>("#close-vault")!;
const replayWorkflowButton = document.querySelector<HTMLButtonElement>("#replay-workflow")!;
const deleteWorkflowButton = document.querySelector<HTMLButtonElement>("#delete-workflow")!;
const replayStatus = document.querySelector<HTMLParagraphElement>("#replay-status")!;
const steps = document.querySelector<HTMLDivElement>("#steps")!;
const review = document.querySelector<HTMLElement>("#review")!;
const workflowName = document.querySelector<HTMLInputElement>("#workflow-name")!;
const nameHint = document.querySelector<HTMLParagraphElement>("#name-hint")!;
const saveButton = document.querySelector<HTMLButtonElement>("#save")!;
const message = document.querySelector<HTMLParagraphElement>("#message")!;
const recordButton = document.querySelector<HTMLButtonElement>("#record")!;
const stopButton = document.querySelector<HTMLButtonElement>("#stop")!;
const installAbletonCheckbox = document.querySelector<HTMLInputElement>("#install-ableton-checkbox")!;
const installAbletonButton = document.querySelector<HTMLButtonElement>("#install-ableton")!;
const installAbletonCustomButton = document.querySelector<HTMLButtonElement>("#install-ableton-custom")!;
const installAbletonStatus = document.querySelector<HTMLParagraphElement>("#install-ableton-status")!;
const abletonBridgeStatus = document.querySelector<HTMLParagraphElement>("#ableton-bridge-status")!;
let savedStatus: string | null = null;
let reviewWasVisible = false;
let apiToken: string | null = null;
let workflows: VaultWorkflow[] = [];
let selectedWorkflow: VaultWorkflow | null = null;
let isSavingWorkflow = false;
let currentMode = "idle";

recordButton.addEventListener("click", async () => {
  savedStatus = null;
  message.textContent = "";
  resetWorkflowName();
  reviewWasVisible = false;
  await invoke("start_recording");
  await refresh();
});

stopButton.addEventListener("click", async () => {
  message.textContent = "";
  if (currentMode === "replaying") {
    await companionFetch<{ status: string }>("/replay/stop", { method: "POST" });
  } else {
    await invoke("stop_recording");
  }
  await refresh();
});

document.querySelector<HTMLButtonElement>("#open-vault")!.addEventListener("click", async () => {
  await chooseWorkflows();
});

installAbletonButton.addEventListener("click", async () => {
  if (!installAbletonCheckbox.checked) {
    setInstallAbletonStatus("failed", "Tick Install Ableton Remote Script first.");
    return;
  }
  await installAbletonRemoteScript(false);
});

installAbletonCustomButton.addEventListener("click", async () => {
  if (!installAbletonCheckbox.checked) {
    setInstallAbletonStatus("failed", "Tick Install Ableton Remote Script first.");
    return;
  }
  await installAbletonRemoteScript(true);
});

closeVaultButton.addEventListener("click", () => {
  vaultDrawer.hidden = true;
});

refreshWorkflowsButton.addEventListener("click", async () => {
  await chooseWorkflows();
});

replayWorkflowButton.addEventListener("click", async () => {
  if (!selectedWorkflow) {
    return;
  }
  replayStatus.hidden = false;
  replayStatus.className = "running";
  replayStatus.textContent = "Replay running...";
  try {
    const result = await companionFetch<{ status?: string; ok?: boolean; pid?: number; error?: string; message?: string; detail?: string; focused_window?: string; target_app?: string }>("/replay", {
      method: "POST",
      body: JSON.stringify({ name: selectedWorkflow.name }),
    });
    const succeeded = result.status === "started" || result.status === "ok" || result.ok === true;
    const aborted = result.status === "aborted" || result.error === "replay aborted";
    replayStatus.className = succeeded || aborted ? "completed" : "failed";
    if (succeeded) {
      const pid = result.pid ? ` (pid ${result.pid})` : "";
      const focused = result.focused_window ? ` - focused ${result.focused_window}` : "";
      replayStatus.textContent = `Replay started${pid}${focused}`;
    } else if (aborted) {
      replayStatus.textContent = result.message ?? "Replay aborted by user";
    } else {
      if (result.error === "failed to focus target window") {
        replayStatus.textContent = `Please open ${result.target_app ?? "the target app"} first, then click Replay.`;
      } else {
        replayStatus.textContent = result.error ?? "Replay failed";
      }
    }
  } catch (error) {
    const message = String(error);
    if (message.toLowerCase().includes("replay aborted")) {
      replayStatus.className = "completed";
      replayStatus.textContent = "Replay aborted by user";
    } else {
      replayStatus.className = "failed";
      replayStatus.textContent = message;
    }
  }
});

deleteWorkflowButton.addEventListener("click", () => {
  void deleteSelectedWorkflow();
});

workflowName.addEventListener("input", () => {
  updateSaveState();
});

saveButton.addEventListener("click", async () => {
  const name = workflowName.value.trim();
  if (!name) {
    showNameRequired();
    return;
  }
  if (isSavingWorkflow) {
    return;
  }
  const keepIndexes = Array.from(steps.querySelectorAll<HTMLInputElement>("input[data-index]"))
    .filter((input) => input.checked)
    .map((input) => Number(input.dataset.index));
  isSavingWorkflow = true;
  updateSaveState();
  message.textContent = "Saving workflow...";
  try {
    const saved = await invoke<string>("save_workflow", {
      request: { name, keep_indexes: keepIndexes },
    });
    let path = saved;
    let slug = "";
    try {
      const parsed = JSON.parse(saved) as { path?: string; slug?: string };
      path = parsed.path ?? saved;
      slug = parsed.slug ?? "";
    } catch {
      path = saved;
    }
    savedStatus = `Saved: ${slug || name}`;
    message.textContent = slug ? `${path} (slug: ${slug})` : path;
    resetWorkflowName();
    await refresh();
  } catch (error) {
    message.textContent = String(error);
  } finally {
    isSavingWorkflow = false;
    updateSaveState();
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

async function chooseWorkflows() {
  try {
    const picked = await invoke<VaultWorkflow[]>("pick_workflows");
    if (picked.length === 0) {
      if (workflows.length === 0) {
        vaultDrawer.hidden = true;
      }
      return;
    }
    workflows = picked;
    selectedWorkflow = workflows[0] ?? null;
    vaultDrawer.hidden = false;
    replayStatus.hidden = true;
    renderWorkflows();
  } catch (error) {
    vaultDrawer.hidden = true;
    message.textContent = `Unable to load workflows: ${String(error)}`;
    workflowActions.hidden = true;
  }
}

async function installAbletonRemoteScript(pickFolder: boolean) {
  installAbletonButton.disabled = true;
  installAbletonCustomButton.disabled = true;
  setInstallAbletonStatus("running", pickFolder ? "Choose Ableton's Remote Scripts folder..." : "Installing Ableton Remote Script...");
  try {
    const result = await invoke<{ installed: boolean; path: string; message: string }>("install_ableton_remote_script_command", {
      request: { pick_folder: pickFolder },
    });
    setInstallAbletonStatus(
      result.installed ? "completed" : "failed",
      `${result.message} Installed at: ${result.path}`,
    );
  } catch (error) {
    setInstallAbletonStatus("failed", String(error));
  } finally {
    installAbletonButton.disabled = false;
    installAbletonCustomButton.disabled = false;
  }
}

function setInstallAbletonStatus(status: "running" | "completed" | "failed", text: string) {
  installAbletonStatus.hidden = false;
  installAbletonStatus.className = `install-status ${status}`;
  installAbletonStatus.textContent = text;
}

async function deleteSelectedWorkflow() {
  if (!selectedWorkflow) {
    return;
  }
  const name = selectedWorkflow.name;
  if (!confirm(`Delete workflow "${name}"?`)) {
    return;
  }
  replayStatus.hidden = false;
  replayStatus.className = "running";
  replayStatus.textContent = "Deleting workflow...";
  try {
    await companionFetch<{ status: string }>("/workflow/delete", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    selectedWorkflow = null;
    replayStatus.className = "completed";
    replayStatus.textContent = "Workflow deleted.";
    workflows = workflows.filter((workflow) => workflow.name !== name);
    selectedWorkflow = workflows[0] ?? null;
    renderWorkflows();
    vaultDrawer.hidden = workflows.length === 0;
  } catch (error) {
    replayStatus.className = "failed";
    replayStatus.textContent = String(error);
  }
}

async function companionFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!apiToken) {
    console.log("[Marouba] Loading companion bearer token");
    apiToken = await invoke<string>("companion_token");
  }
  const url = `http://localhost:7842${path}`;
  const request = {
    ...init,
    headers: {
      Authorization: `Bearer ${apiToken}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  };
  console.log("[Marouba] Companion fetch", { method: request.method ?? "GET", url });
  let response: Response;
  try {
    response = await fetch(url, request);
  } catch (error) {
    console.error("[Marouba] Companion fetch failed before response", { url, error });
    throw error;
  }
  const body = await response.json().catch((error) => {
    console.error("[Marouba] Companion response JSON parse failed", { url, error });
    return {};
  });
  console.log("[Marouba] Companion response", { url, status: response.status, body });
  if (!response.ok) {
    console.error("[Marouba] Companion request failed", { url, status: response.status, body });
    throw new Error(body.error ?? `HTTP ${response.status}`);
  }
  return body as T;
}

function renderWorkflows() {
  workflowList.replaceChildren(
    ...workflows.map((workflow) => {
      const row = document.createElement("button");
      row.className = "workflow-row";
      row.classList.toggle("selected", selectedWorkflow?.name === workflow.name);
      row.type = "button";

      const name = document.createElement("span");
      name.className = "workflow-name";
      name.textContent = workflow.name;

      row.append(name);
      row.addEventListener("click", () => {
        selectedWorkflow = workflow;
        replayStatus.hidden = true;
        renderWorkflows();
      });
      return row;
    }),
  );
  if (workflows.length === 0) {
    workflowList.textContent = "Choose one or more workflow files.";
  }
  workflowActions.hidden = selectedWorkflow === null;
  vaultDrawer.hidden = workflows.length === 0;
}

function render(status: RecordingStatus) {
  const isRecording = status.mode === "recording";
  const isReplaying = status.mode === "replaying";
  currentMode = status.mode;
  mode.textContent = savedStatus ?? (isRecording ? "Recording..." : isReplaying ? "Replaying..." : "Idle");
  dot.classList.toggle("recording", status.mode === "recording");
  recordButton.disabled = isRecording;
  stopButton.disabled = !isRecording && !isReplaying;
  const title = status.active_window.title || "Marouba";
  const appName = status.active_window.app_name || "";
  windowLabel.textContent = appName && appName !== "unknown" ? `${appName} - ${title}` : title;
  renderAbletonBridgeStatus(status.ableton_bridge);

  actions.replaceChildren(
    ...status.last_actions.map((label) => {
      const item = document.createElement("li");
      item.textContent = label;
      return item;
    }),
  );

  const reviewVisible = status.steps.length > 0 && status.mode !== "recording";
  review.hidden = !reviewVisible;
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
  if (reviewVisible && !reviewWasVisible) {
    workflowName.focus();
  }
  reviewWasVisible = reviewVisible;
  updateSaveState();
}

function renderAbletonBridgeStatus(health?: AbletonBridgeHealth) {
  if (!health) {
    abletonBridgeStatus.className = "bridge-status unavailable";
    abletonBridgeStatus.textContent = "Ableton bridge: unavailable";
    return;
  }
  abletonBridgeStatus.className = `bridge-status ${health.status}`;
  const portInfo = `${health.send_port}/${health.recv_port}`;
  if (health.status === "ok") {
    abletonBridgeStatus.textContent = `Ableton bridge: live (${portInfo})`;
  } else {
    abletonBridgeStatus.textContent = `Ableton bridge: ${health.status} (${health.message ?? "no response"})`;
  }
}

function updateSaveState() {
  const hasName = workflowName.value.trim().length > 0;
  saveButton.disabled = isSavingWorkflow;
  saveButton.setAttribute("aria-disabled", hasName && !isSavingWorkflow ? "false" : "true");
  if (hasName) {
    nameHint.hidden = true;
    workflowName.classList.remove("invalid");
  }
}

function resetWorkflowName() {
  workflowName.value = "";
  nameHint.hidden = true;
  workflowName.classList.remove("invalid", "shake");
  updateSaveState();
}

function showNameRequired() {
  nameHint.hidden = false;
  workflowName.classList.remove("shake");
  workflowName.classList.add("invalid");
  void workflowName.offsetWidth;
  workflowName.classList.add("shake");
  workflowName.focus();
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
vaultDrawer.hidden = true;
setInterval(refresh, 1500);
