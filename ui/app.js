const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send");
const statusBadge = document.querySelector("#status");
const policyDetail = document.querySelector("#policy-detail");
const packChip = document.querySelector("#pack-chip");
const notice = document.querySelector("#notice");
const activityList = document.querySelector("#activity");
const activityButton = document.querySelector("#refresh-activity");
let conversationId = crypto.randomUUID();
let ready = false;
let sending = false;
let checkingStatus = false;

function addMessage(role, text, options = {}) {
  const article = document.createElement("article");
  article.className = `message message-${role}${options.denied ? " message-denial" : ""}`;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Riri";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = text || (role === "assistant" ? "The agent returned no text." : "");
  article.append(label, body);
  if (options.alternative) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "safe-action";
    button.textContent = "Try the safe alternative";
    button.addEventListener("click", () => submitPrompt(options.alternative));
    article.append(button);
  }
  messages.append(article);
  article.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showNotice(text) {
  notice.textContent = text;
  notice.hidden = !text;
}

function updateComposer() {
  sendButton.disabled = !ready || sending || !promptInput.value.trim();
  promptInput.disabled = !ready || sending;
}

function renderPolicyStatus(status) {
  ready = status.ready === true;
  statusBadge.textContent = ready ? "POLICIES VERIFIED" : "POLICY CHECK BLOCKED";
  statusBadge.className = `status ${ready ? "status-ready" : "status-blocked"}`;
  packChip.textContent = ready
    ? `Pack · ${status.version} · ${status.cli}`
    : "Policy pack · unavailable";
  policyDetail.replaceChildren();
  const rows = ready
    ? [
        ["Pack", `${status.pack_id}@${status.version}`],
        ["Agent scope", status.cli],
        ["Effect", "Enforce"],
        ["Policies", String(status.policy_count)],
        ["Intake model", status.classifier_model],
      ]
    : [["Status", "Fail closed"], ["Prompt path", "Not forwarded"]];
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    row.className = "policy-row";
    const key = document.createElement("span");
    key.textContent = label;
    const content = document.createElement("span");
    content.textContent = value;
    if (label === "Effect" || label === "Status") {
      content.className = ready ? "policy-status-ready" : "policy-status-blocked";
    }
    row.append(key, content);
    policyDetail.append(row);
  }
  if (!ready) showNotice(status.message || "The policy check failed. Prompts are paused.");
  else showNotice("");
  updateComposer();
}

async function refreshStatus() {
  if (checkingStatus) return;
  checkingStatus = true;
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error(`Status request failed (${response.status})`);
    renderPolicyStatus(await response.json());
  } catch {
    renderPolicyStatus({
      ready: false,
      message: "Riri could not verify its local policy service. No prompt will be forwarded.",
    });
  } finally {
    checkingStatus = false;
  }
}

function friendlyEventName(eventType) {
  return eventType.replaceAll("_", " ");
}

async function refreshActivity() {
  try {
    const response = await fetch("/api/activity?limit=20");
    if (!response.ok) throw new Error("Activity is unavailable");
    const { events } = await response.json();
    activityList.replaceChildren();
    if (!events.length) {
      const empty = document.createElement("li");
      empty.className = "activity-empty";
      empty.textContent = "No activity yet.";
      activityList.append(empty);
      return;
    }
    for (const event of events) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = friendlyEventName(event.event_type);
      const time = document.createElement("time");
      time.dateTime = event.created_at;
      time.textContent = new Date(event.created_at).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
      item.append(label, time);
      activityList.append(item);
    }
  } catch {
    activityList.replaceChildren();
    const unavailable = document.createElement("li");
    unavailable.className = "activity-empty";
    unavailable.textContent = "Local activity is unavailable.";
    activityList.append(unavailable);
  }
}

async function submitPrompt(text) {
  const prompt = text.trim();
  if (!prompt || !ready || sending) return;
  sending = true;
  showNotice("");
  addMessage("user", prompt);
  promptInput.value = "";
  updateComposer();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, prompt }),
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.detail || "Riri could not complete the request.");
      if (response.status === 503) {
        ready = false;
        updateComposer();
        await refreshStatus();
      }
      throw error;
    }
    addMessage("assistant", result.text, {
      denied: result.policy_denials.length > 0,
      alternative: result.safe_alternative,
    });
  } catch (error) {
    showNotice(error.message || "The local agent could not complete this request.");
  } finally {
    sending = false;
    updateComposer();
    await refreshStatus();
    await refreshActivity();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitPrompt(promptInput.value);
});

promptInput.addEventListener("input", updateComposer);
promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

activityButton.addEventListener("click", refreshActivity);
renderPolicyStatus({ ready: false, message: "Checking the local policy service…" });
refreshStatus();
refreshActivity();
setInterval(() => {
  if (!ready && !sending) refreshStatus();
}, 5000);
