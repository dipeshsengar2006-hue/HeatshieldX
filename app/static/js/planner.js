(() => {
  const mapElement = document.querySelector("#map");
  if (!mapElement || typeof L === "undefined") return;

  const lat = Number(document.body.dataset.lat);
  const lon = Number(document.body.dataset.lon);
  const map = L.map(mapElement, { zoomControl: true }).setView([lat, lon], 15);
  let mapResizeFrame;
  const invalidateMapSize = () => {
    window.cancelAnimationFrame(mapResizeFrame);
    mapResizeFrame = window.requestAnimationFrame(() => map.invalidateSize({ pan: false }));
  };
  window.addEventListener("resize", invalidateMapSize);
  if ("ResizeObserver" in window) new ResizeObserver(invalidateMapSize).observe(mapElement);
  const slider = document.querySelector("#exposure-slider");
  const timeOutput = document.querySelector("#exposure-time");
  const statusLabel = document.querySelector("#exposure-status-label");
  const exposureStatus = document.querySelector("#exposure-status");
  const modeBadge = document.querySelector("#exposure-mode");
  const buildingsToggle = document.querySelector("#buildings-toggle");
  const whyPanel = document.querySelector("#why-panel");
  const compareButton = document.querySelector("#compare-hottest");
  const comparisonPanel = document.querySelector("#comparison-panel");
  const resourceForm = document.querySelector("#resource-form");
  const optimizeButton = document.querySelector("#optimize-response");
  const resourceStatus = document.querySelector("#resource-status");
  const deploymentPlan = document.querySelector("#deployment-plan");
  const impactPanel = document.querySelector("#impact-panel");
  const impactMetrics = document.querySelector("#impact-metrics");
  const impactNote = document.querySelector("#impact-note");
  const riskClassCounts = document.querySelector("#risk-class-counts");
  const scenarioButtons = document.querySelectorAll("[data-scenario]");
  let buildingLayer;
  let facilityLayer;
  let riskLayer;
  let proposedLayer;
  let selectedKeys = new Set();
  let riskRequestVersion = 0;
  let hasFittedBounds = false;
  let activePlanId;
  let scenario = "before";

  // Tiles are optional: essential streets and interactions use cached API data.
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  const formatTime = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  const activeTime = () => formatTime(Number(slider?.value || 540));
  const updateCopilotContext = (details = {}) => {
    if (!window.heatshieldCopilot) return;
    const water = document.querySelector("#water-points")?.value || "0";
    const cooling = document.querySelector("#cooling-centres")?.value || "0";
    const shade = document.querySelector("#shade-structures")?.value || "0";
    window.heatshieldCopilot.setContext({
      view: "planner", time: activeTime(), plan_id: activePlanId,
      plan_counts: { water, cooling, shade }, ...details,
    });
  };
  const riskColor = (riskClass) => ({ LOW: "#2e8b57", MODERATE: "#e2a132", HIGH: "#e76f34", CRITICAL: "#b42318" }[riskClass] || "#627d98");
  const append = (parent, tag, text, className) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    parent.append(element);
    return element;
  };
  const metric = (parent, label, value, definition) => {
    const item = append(parent, "div", undefined, "metric");
    const heading = append(item, "dt", label);
    if (definition) { heading.title = definition; heading.setAttribute("aria-label", `${label}: ${definition}`); }
    append(item, "dd", value);
  };

  const updateMapStyles = () => {
    if (!riskLayer) return;
    riskLayer.eachLayer((layer) => {
      const feature = layer.feature;
      const selected = selectedKeys.has(feature?.properties?.canonical_street_key);
      layer.setStyle({
        color: selected ? "#102a43" : riskColor(feature.properties.risk_class),
        weight: selected ? 6 : 4,
        opacity: 0.95,
      });
    });
  };

  const makeLayerKeyboardAccessible = (layer, feature) => {
    const path = layer.getElement?.();
    if (!path) return;
    const id = feature.properties.canonical_street_key;
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "button");
    path.setAttribute("aria-label", `Explain street ${id}`);
    path.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectStreet(id);
      }
    });
  };

  const loadBuildings = async () => {
    try {
      const response = await fetch("/api/buildings");
      if (!response.ok) throw new Error("Building cache is unavailable.");
      const collection = await response.json();
      buildingLayer = L.geoJSON(collection, { style: { color: "#657483", weight: 1, fillColor: "#7d8a97", fillOpacity: 0.3 } });
      if (buildingsToggle?.checked) buildingLayer.addTo(map);
    } catch (error) {
      console.warn("HeatShield building data is unavailable.", error);
    }
  };

  const loadFacilities = async () => {
    try {
      const response = await fetch("/api/facilities");
      if (!response.ok) throw new Error("Facility cache is unavailable.");
      const collection = await response.json();
      facilityLayer = L.geoJSON(collection, {
        pointToLayer: (feature, location) => L.circleMarker(location, {
          radius: 4, color: "#4b5563", weight: 1, fillColor: "#9ca3af", fillOpacity: 0.9,
        }).bindTooltip(`Observed OSM ${feature.properties.facility_type || "facility"}: ${feature.properties.name || "Unnamed"}`),
      }).addTo(map);
    } catch (error) {
      console.warn("HeatShield facility data is unavailable.", error);
    }
  };

  const renderWhy = (payload) => {
    if (!whyPanel) return;
    const { street } = payload;
    whyPanel.replaceChildren();
    append(whyPanel, "p", "Street explanation", "eyebrow");
    const streetHeading = append(whyPanel, "h2", street.street_name || street.canonical_street_key, "street-title");
    streetHeading.title = street.street_name || street.canonical_street_key;
    append(whyPanel, "p", `Street ID: ${street.canonical_street_key}`);
    const grid = append(whyPanel, "dl", undefined, "metric-grid");
    metric(grid, "Score / class", `${Number(street.risk_score).toFixed(1)} / ${street.risk_class}`, "A modelled prioritization score from 0 to 100, not a medical threshold.");
    metric(grid, "Solar exposure", `${street.solar_exposure_level} (${Number(street.exposure_value).toFixed(2)})`, "The modelled share of direct street exposure at the selected time.");
    metric(grid, "Shade", `${street.shade_level} (${Number(street.shade_fraction).toFixed(2)})`, "The modelled share of the street shaded at the selected time.");
    metric(grid, "Vulnerability", `${street.vulnerability_level} — estimated, density-based proxy`, "An estimated prioritization input based on the configured vulnerability proxy.");
    metric(grid, "Cooling access", `${street.cooling_access_level} (${Number(street.access_penalty).toFixed(2)})`, "A modelled access penalty based on recorded cooling and water facilities.");
    if (!street.water_available && !street.cooling_available) {
      append(whyPanel, "p", "No recorded water/cooling facilities in OSM for this area.", "facility-note");
    }
    append(whyPanel, "p", payload.primary_drivers_sentence);
    append(whyPanel, "h3", "Driver contributions");
    const drivers = append(whyPanel, "ul", undefined, "driver-list");
    payload.drivers.forEach((driver) => append(drivers, "li", `${driver.label}: ${driver.level} (${Math.round(driver.relative_contribution * 100)}%)`));
    const labels = append(whyPanel, "ul", undefined, "status-list");
    payload.status_labels.forEach((label) => {
      const item = append(labels, "li", label);
      item.title = payload.status_label_details?.[label] || label;
    });
  };

  async function selectStreet(streetId, { preserveHighlights = false } = {}) {
    if (!preserveHighlights) selectedKeys = new Set([streetId]);
    updateMapStyles();
    try {
      const response = await fetch(`/api/segments/${encodeURIComponent(streetId)}/why?time=${encodeURIComponent(activeTime())}`);
      if (!response.ok) throw new Error("Street explanation is unavailable.");
      const payload = await response.json();
      selectedKeys.add(payload.street.canonical_street_key);
      updateMapStyles();
      renderWhy(payload);
      updateCopilotContext({
        selected_segment_id: payload.street.canonical_street_key,
        street_name: payload.street.street_name || payload.street.canonical_street_key,
      });
    } catch (error) {
      if (whyPanel) {
        whyPanel.replaceChildren();
        append(whyPanel, "h2", "Street explanation unavailable");
        append(whyPanel, "p", "The selected cached street explanation could not be loaded. Try another time or rerun the risk precompute step.", "panel-empty");
      }
      console.warn("HeatShield street explanation is unavailable.", error);
    }
  }

  const planRiskUrl = (requestedTime) => {
    const query = new URLSearchParams({ time: requestedTime });
    if (scenario === "after" && activePlanId) query.set("plan_id", activePlanId);
    return `/api/risk?${query.toString()}`;
  };

  const showRisk = async (requestedTime) => {
    const requestVersion = ++riskRequestVersion;
    if (exposureStatus) exposureStatus.textContent = `Loading cached modelled prioritization for ${requestedTime}...`;
    try {
      const response = await fetch(planRiskUrl(requestedTime));
      if (!response.ok) throw new Error("Risk cache is unavailable.");
      const collection = await response.json();
      if (requestVersion !== riskRequestVersion) return;
      if (riskLayer) map.removeLayer(riskLayer);
      riskLayer = L.geoJSON(collection, {
        style: (feature) => ({ color: riskColor(feature.properties.risk_class), weight: 4, opacity: 0.95 }),
        onEachFeature: (feature, layer) => {
          layer.on("click", () => selectStreet(feature.properties.canonical_street_key));
          layer.on("add", () => makeLayerKeyboardAccessible(layer, feature));
        },
      }).addTo(map);
      updateMapStyles();
      if (!hasFittedBounds && riskLayer.getBounds().isValid()) {
        map.fitBounds(riskLayer.getBounds(), { padding: [24, 24] });
        hasFittedBounds = true;
      }
      const metadata = collection.metadata || {};
      const interpolated = Boolean(metadata.interpolated);
      if (timeOutput) timeOutput.textContent = requestedTime;
      if (statusLabel) statusLabel.textContent = interpolated ? "Interpolated" : "Modelled";
      if (modeBadge) {
        const geometric = metadata.computation_mode === "geometric";
        modeBadge.textContent = geometric ? "Geometric shadow mode" : "Estimated Exposure Mode";
        modeBadge.dataset.mode = geometric ? "geometric" : "estimated";
      }
      if (exposureStatus) exposureStatus.textContent = interpolated
        ? `${requestedTime} is interpolated from cached ${metadata.interpolation_lower_time} and ${metadata.interpolation_upper_time} model snapshots.`
        : `${requestedTime} uses a cached modelled-prioritization snapshot for ${metadata.street_deduplication?.unique_street_count ?? "all"} unique streets.`;
      if (comparisonPanel) comparisonPanel.hidden = true;
      if (activePlanId) refreshRiskClassCounts();
    } catch (error) {
      if (exposureStatus) exposureStatus.textContent = "Risk cache is unavailable. Run `python scripts/precompute_risk.py`; cached base map data remains available.";
      console.warn("HeatShield risk data is unavailable.", error);
    }
  };

  const displayValue = (value) => {
    if (typeof value === "number") return `${value >= 0 ? "" : ""}${value.toFixed(3)}`;
    if (value && typeof value === "object") return Object.entries(value).map(([key, count]) => `${key}: ${count}`).join(", ");
    return value ?? "—";
  };

  const metricLabel = (key) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

  const renderImpact = (plan) => {
    if (!impactPanel || !impactMetrics) return;
    impactPanel.hidden = false;
    impactMetrics.replaceChildren();
    Object.entries(plan.metrics).forEach(([key, value]) => {
      const row = document.createElement("tr");
      const label = append(row, "th", `${metricLabel(key)} — ${value.definition}`);
      label.scope = "row";
      label.title = value.definition;
      append(row, "td", displayValue(value.before));
      append(row, "td", displayValue(value.modelled_after));
      append(row, "td", displayValue(value.delta));
      impactMetrics.append(row);
    });
    const unavailable = Object.values(plan.metrics).some((value) => String(value.before).includes("Data unavailable (no recorded facility)"));
    if (impactNote) impactNote.hidden = !unavailable;
    scenarioButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.scenario === scenario)));
    refreshRiskClassCounts();
  };

  const countClasses = (collection) => collection.features.reduce((counts, feature) => {
    const riskClass = feature.properties.risk_class;
    counts[riskClass] = (counts[riskClass] || 0) + 1;
    return counts;
  }, {});

  async function refreshRiskClassCounts() {
    if (!activePlanId || !riskClassCounts) return;
    try {
      const time = activeTime();
      const [beforeResponse, afterResponse] = await Promise.all([
        fetch(`/api/risk?time=${encodeURIComponent(time)}`),
        fetch(`/api/risk?time=${encodeURIComponent(time)}&plan_id=${encodeURIComponent(activePlanId)}`),
      ]);
      if (!beforeResponse.ok || !afterResponse.ok) throw new Error("Risk counts unavailable");
      const [before, after] = await Promise.all([beforeResponse.json(), afterResponse.json()]);
      riskClassCounts.textContent = `Risk-class street counts at ${time}${before.metadata?.interpolated ? " (Interpolated)" : ""} — Before: ${displayValue(countClasses(before))}. Modelled After: ${displayValue(countClasses(after))}.`;
    } catch (error) {
      riskClassCounts.textContent = "Risk-class counts are unavailable for the selected time.";
      console.warn("HeatShield impact counts are unavailable.", error);
    }
  }

  const renderProposedSites = (plan) => {
    if (proposedLayer) map.removeLayer(proposedLayer);
    proposedLayer = L.layerGroup();
    selectedKeys = new Set(plan.priorities.filter((item) => item.type === "shade_structures").map((item) => item.street_canonical_key));
    plan.priorities.forEach((item) => {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: 7, color: "#174a7e", weight: 2, fillColor: "#5bb6e5", fillOpacity: 0.9,
      }).bindTooltip(`Proposed ${item.type_label}: ${item.street_name || item.street_canonical_key}`);
      marker.on("click", () => focusPlanItem(item));
      proposedLayer.addLayer(marker);
    });
    proposedLayer.addTo(map);
    updateMapStyles();
  };

  const focusPlanItem = (item) => {
    map.setView([item.lat, item.lon], Math.max(map.getZoom(), 17));
    selectStreet(item.street_canonical_key, { preserveHighlights: true });
  };

  const renderDeploymentPlan = (plan) => {
    if (!deploymentPlan) return;
    deploymentPlan.replaceChildren();
    plan.priorities.forEach((item) => {
      const entry = append(deploymentPlan, "li");
      entry.tabIndex = 0;
      entry.setAttribute("role", "button");
      entry.setAttribute("aria-label", `Focus proposed ${item.type_label} on ${item.street_name || item.street_canonical_key}`);
      append(entry, "strong", `${item.priority}. ${item.type_label} — ${item.street_name || item.street_canonical_key}`);
      append(entry, "span", `Street ID: ${item.street_canonical_key}. ${Math.round(item.share_of_total_reduction * 100)}% of total modelled reduction.`);
      append(entry, "span", item.explanation);
      entry.addEventListener("click", () => focusPlanItem(item));
      entry.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); focusPlanItem(item); }
      });
    });
  };

  const optimizeResponse = async (event) => {
    event.preventDefault();
    if (!resourceForm || !optimizeButton) return;
    const formData = new FormData(resourceForm);
    const values = Object.fromEntries(["water_points", "cooling_centres", "shade_structures"].map((key) => [key, Number(formData.get(key))]));
    optimizeButton.disabled = true;
    optimizeButton.textContent = "Optimizing…";
    if (resourceStatus) { resourceStatus.classList.remove("error"); resourceStatus.textContent = "Building the modelled deployment plan…"; }
    try {
      const response = await fetch("/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Optimization could not be completed.");
      activePlanId = payload.plan_id;
      scenario = "after";
      renderDeploymentPlan(payload);
      renderProposedSites(payload);
      renderImpact(payload);
      if (resourceStatus) resourceStatus.textContent = `Modelled plan ${payload.plan_id} is ready.`;
      updateCopilotContext();
      showRisk(activeTime());
    } catch (error) {
      if (resourceStatus) { resourceStatus.classList.add("error"); resourceStatus.textContent = `Unable to optimize: ${error.message}`; }
    } finally {
      optimizeButton.disabled = false;
      optimizeButton.textContent = "Optimize Response";
    }
  };

  const comparisonCard = (label, street) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "comparison-card";
    append(card, "h3", label);
    append(card, "p", street.street_name || street.canonical_street_key);
    append(card, "p", `Exposure ${Number(street.exposure_value).toFixed(2)} · Shade ${Number(street.shade_fraction).toFixed(2)}`);
    append(card, "p", `Vulnerability ${street.vulnerability_level} · Cooling access ${street.cooling_access_level}`);
    append(card, "p", `Final risk ${Number(street.final_risk_raw).toFixed(3)} · Score ${Number(street.risk_score).toFixed(1)}`);
    card.addEventListener("click", () => selectStreet(street.canonical_street_key, { preserveHighlights: true }));
    return card;
  };

  const showComparison = async () => {
    if (!comparisonPanel) return;
    comparisonPanel.hidden = false;
    comparisonPanel.replaceChildren();
    append(comparisonPanel, "h2", "Why not the hottest?");
    append(comparisonPanel, "p", "Loading comparison...", "panel-empty");
    try {
      const response = await fetch(`/api/compare/hottest?time=${encodeURIComponent(activeTime())}`);
      if (!response.ok) throw new Error("Comparison is unavailable.");
      const payload = await response.json();
      selectedKeys = new Set([payload.hottest.canonical_street_key, payload.highest_risk.canonical_street_key]);
      updateMapStyles();
      comparisonPanel.replaceChildren();
      append(comparisonPanel, "h2", "Why not the hottest?");
      append(comparisonPanel, "p", payload.explanation);
      append(comparisonPanel, "p", `${payload.hottest_tie_count} streets tie for the highest exposure; their risk ranges from ${Number(payload.hottest_tie_risk_score_min).toFixed(1)} to ${Number(payload.hottest_tie_risk_score_max).toFixed(1)}. Highest-risk tie count: ${payload.highest_risk_tie_count}.`, "panel-empty");
      const cards = append(comparisonPanel, "div", undefined, "comparison-cards");
      cards.append(comparisonCard("Highest exposure", payload.hottest), comparisonCard("Highest modelled priority", payload.highest_risk));
    } catch (error) {
      comparisonPanel.replaceChildren();
      append(comparisonPanel, "h2", "Comparison unavailable");
      append(comparisonPanel, "p", "The cached comparison could not be loaded. Rerun the risk precompute step and try again.", "panel-empty");
      console.warn("HeatShield comparison is unavailable.", error);
    }
  };

  buildingsToggle?.addEventListener("change", () => {
    if (!buildingLayer) return;
    if (buildingsToggle.checked) buildingLayer.addTo(map);
    else map.removeLayer(buildingLayer);
  });
  slider?.addEventListener("input", () => { updateCopilotContext(); showRisk(activeTime()); });
  compareButton?.addEventListener("click", showComparison);
  resourceForm?.addEventListener("submit", optimizeResponse);
  scenarioButtons.forEach((button) => button.addEventListener("click", () => {
    if (!activePlanId) return;
    scenario = button.dataset.scenario;
    scenarioButtons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    showRisk(activeTime());
  }));
  loadBuildings();
  loadFacilities();
  updateCopilotContext();
  showRisk(activeTime());
})();
