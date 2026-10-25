const messages = document.querySelector("#messages");
const form = document.querySelector("#composer");
const promptInput = document.querySelector("#prompt");
const sendButton = document.querySelector("#send");
const statusBadge = document.querySelector("#status");
const policyDetail = document.querySelector("#policy-detail");
const policyIndicator = document.querySelector(".policy-indicator");
const notice = document.querySelector("#notice");
const welcome = document.querySelector("#welcome");
const newChatButton = document.querySelector("#new-chat");
let conversationId = crypto.randomUUID();
let ready = false;
let sending = false;
let checkingStatus = false;

function addMessage(role, text, options = {}) {
  welcome.hidden = true;
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
  policyIndicator.className = `policy-indicator ${ready ? "indicator-ready" : "indicator-blocked"}`;
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

function startNewChat() {
  if (sending) return;
  conversationId = crypto.randomUUID();
  messages.replaceChildren();
  welcome.hidden = false;
  promptInput.value = "";
  showNotice("");
  updateComposer();
  promptInput.focus();
}

newChatButton.addEventListener("click", startNewChat);
document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => submitPrompt(button.dataset.prompt || ""));
});
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    startNewChat();
  }
});

renderPolicyStatus({ ready: false, message: "Checking the local policy service…" });
refreshStatus();
setInterval(() => {
  if (!ready && !sending) refreshStatus();
}, 5000);
