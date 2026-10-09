(() => {
  "use strict";

  const root = document.getElementById("copilot-root");
  const catalogNode = document.getElementById("copilot-catalogs");
  if (!root || !catalogNode) return;

  const catalogs = JSON.parse(catalogNode.textContent || "{}");
  const english = catalogs.en || {};
  const body = document.body;
  const panel = document.getElementById("copilot-panel");
  const backdrop = document.getElementById("copilot-backdrop");
  const openButton = document.getElementById("copilot-open");
  const closeButton = document.getElementById("copilot-close");
  const contextNode = document.getElementById("copilot-context");
  const examplesNode = document.getElementById("copilot-example-list");
  const conversationNode = document.getElementById("copilot-conversation");
  const form = document.getElementById("copilot-form");
  const input = document.getElementById("copilot-input");
  const sendButton = document.getElementById("copilot-send");
  const clearButton = document.getElementById("copilot-clear");
  const counter = document.getElementById("copilot-counter");
  const errorNode = document.getElementById("copilot-error");
  const retryButton = document.getElementById("copilot-retry");
  const state = {
    language: document.documentElement.lang === "hi" ? "hi" : "en",
    context: { view: body.dataset.copilotView || "planner" },
    conversation: [],
    lastMessage: "",
    pending: false,
    opener: null,
  };

  const message = (id, params = {}) => {
    const template = (catalogs[state.language] || english)[id] || english[id] || id;
    return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (placeholder, name) => (
      Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder
    ));
  };
  const text = (tag, value, className) => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const contextForRequest = () => {
    const context = state.context;
    const allowed = ["view", "time", "selected_segment_id", "plan_id", "origin", "destination"];
    return Object.fromEntries(allowed.filter((key) => context[key] !== undefined && context[key] !== null && context[key] !== "").map((key) => [key, context[key]]));
  };
  const updateCounter = () => { counter.value = message("copilot_character_count", { count: input.value.length }); counter.textContent = counter.value; };
  const contextLabel = () => {
    const context = state.context;
    if (context.plan_id && context.plan_counts) return message("copilot_context_plan", context.plan_counts);
    if (context.view === "citizen" && context.origin_name && context.destination_name) {
      return message("copilot_context_route", { origin: context.origin_name, destination: context.destination_name, time: context.time || "--:--" });
    }
    if (context.street_name) return message("copilot_context_street", { name: context.street_name, time: context.time || "--:--" });
    return message("copilot_context_none");
  };
  const exampleIds = () => state.context.view === "citizen"
    ? ["copilot_example_route", "copilot_example_break", "copilot_example_heat", "copilot_example_height"]
    : ["copilot_example_risk", "copilot_example_plan", "copilot_example_data", "copilot_example_platform"];
  const renderExamples = () => {
    examplesNode.replaceChildren();
    exampleIds().forEach((id) => {
      const button = text("button", message(id), "copilot-chip");
      button.type = "button";
      button.addEventListener("click", () => {
        input.value = message(id);
        updateCounter();
        sendMessage();
      });
      examplesNode.append(button);
    });
  };
  const renderConversation = () => {
    conversationNode.replaceChildren();
    state.conversation.forEach((entry) => {
      const item = document.createElement("li");
      item.className = `copilot-message copilot-message-${entry.role}${entry.data_unavailable ? " copilot-message-neutral" : ""}`;
      if (entry.role === "user") {
        item.append(text("p", entry.text));
      } else if (entry.loading) {
        item.append(text("p", message("copilot_loading"), "copilot-loading"));
      } else {
        const heading = document.createElement("div");
        heading.className = "copilot-answer-meta";
        heading.append(text("span", message(entry.mode === "llm" ? "copilot_ai_assisted" : "copilot_template"), "copilot-status-badge"));
        if (entry.data_unavailable) heading.append(text("span", message("copilot_data_unavailable"), "copilot-status-badge neutral"));
        item.append(heading, text("p", entry.answer || "", "copilot-answer"));
        if (Array.isArray(entry.sources) && entry.sources.length) {
          const sources = document.createElement("div");
          sources.className = "copilot-sources";
          entry.sources.forEach((source) => sources.append(text("span", `${source.type}: ${source.label}`, "copilot-source-chip")));
          item.append(sources);
        }
        const details = document.createElement("details");
        details.className = "copilot-facts";
        details.append(text("summary", message("copilot_facts_title")));
        const facts = entry.facts_used && typeof entry.facts_used === "object" ? Object.entries(entry.facts_used) : [];
        details.append(text("h4", message("copilot_facts")));
        if (facts.length) {
          const list = document.createElement("dl");
          facts.forEach(([key, value]) => { list.append(text("dt", key), text("dd", typeof value === "string" ? value : JSON.stringify(value))); });
          details.append(list);
        } else details.append(text("p", message("copilot_no_facts")));
        details.append(text("h4", message("copilot_assumptions")));
        const assumptions = document.createElement("ul");
        (entry.assumptions || []).forEach((assumption) => assumptions.append(text("li", assumption)));
        details.append(assumptions);
        item.append(details);
      }
      conversationNode.append(item);
    });
    conversationNode.scrollTop = conversationNode.scrollHeight;
  };
  const renderChrome = () => {
    document.querySelectorAll("[data-copilot-i18n]").forEach((node) => { node.textContent = message(node.dataset.copilotI18n); });
    document.querySelectorAll("[data-copilot-i18n-placeholder]").forEach((node) => { node.placeholder = message(node.dataset.copilotI18nPlaceholder); });
    document.querySelectorAll("[data-copilot-i18n-aria-label]").forEach((node) => { node.setAttribute("aria-label", message(node.dataset.copilotI18nAriaLabel)); });
    document.querySelectorAll("[data-copilot-language]").forEach((node) => node.setAttribute("aria-pressed", String(node.dataset.copilotLanguage === state.language)));
    contextNode.textContent = contextLabel();
    renderExamples(); updateCounter(); renderConversation();
  };
  const setError = (id) => {
    if (!id) { errorNode.hidden = true; retryButton.hidden = true; return; }
    errorNode.textContent = message(id); errorNode.hidden = false; retryButton.hidden = false;
  };
  const setPending = (pending) => { state.pending = pending; sendButton.disabled = pending; input.disabled = pending; };
  const focusable = () => [...panel.querySelectorAll('button:not([disabled]), textarea:not([disabled]), [href], details, [tabindex]:not([tabindex="-1"])')].filter((node) => !node.hidden);
  const closePanel = () => { panel.hidden = true; backdrop.hidden = true; openButton.setAttribute("aria-expanded", "false"); (state.opener || openButton).focus(); };
  const openPanel = () => { state.opener = document.activeElement; panel.hidden = false; backdrop.hidden = false; openButton.setAttribute("aria-expanded", "true"); renderChrome(); input.focus(); };
  async function sendMessage() {
    const value = input.value.trim();
    if (!value || state.pending) return;
    if (value.length > 500) { setError("copilot_error_422"); return; }
    setError(""); state.lastMessage = value;
    state.conversation.push({ role: "user", text: value }, { role: "assistant", loading: true });
    input.value = ""; updateCounter(); renderConversation(); setPending(true);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(body.dataset.copilotApi || "/api/copilot", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ message: value, ui_language: state.language, context: contextForRequest() }),
      });
      if (!response.ok) { setError(response.status === 422 ? "copilot_error_422" : "copilot_error_unavailable"); throw new Error("Copilot request failed"); }
      const payload = await response.json();
      state.conversation[state.conversation.length - 1] = { role: "assistant", ...payload };
      setError("");
    } catch (error) {
      state.conversation.pop();
      if (!errorNode.hidden) { /* The response supplied a readable error. */ }
      else setError(error.name === "AbortError" ? "copilot_error_timeout" : "copilot_error_network");
    } finally {
      window.clearTimeout(timeout); setPending(false); renderConversation();
    }
  }

  form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(); });
  input.addEventListener("input", updateCounter);
  clearButton.addEventListener("click", () => { state.conversation = []; state.lastMessage = ""; setError(""); renderConversation(); input.focus(); });
  retryButton.addEventListener("click", () => { input.value = state.lastMessage; updateCounter(); sendMessage(); });
  openButton.addEventListener("click", openPanel);
  closeButton.addEventListener("click", closePanel);
  backdrop.addEventListener("click", closePanel);
  document.addEventListener("keydown", (event) => {
    if (panel.hidden) return;
    if (event.key === "Escape") { event.preventDefault(); closePanel(); return; }
    if (event.key !== "Tab") return;
    const items = focusable(); if (!items.length) return;
    const first = items[0]; const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  document.querySelectorAll("[data-copilot-language]").forEach((button) => button.addEventListener("click", () => {
    setLanguage(button.dataset.copilotLanguage);
  }));
  function setLanguage(language) {
    state.language = language === "hi" ? "hi" : "en";
    document.documentElement.lang = state.language;
    renderChrome();
  }
  window.heatshieldCopilot = {
    setContext: (context) => { state.context = { ...state.context, ...context }; contextNode.textContent = contextLabel(); renderExamples(); },
    setLanguage,
  };
  renderChrome();
})();
