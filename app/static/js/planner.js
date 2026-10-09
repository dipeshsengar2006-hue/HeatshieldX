(() => {
  const mapElement = document.querySelector("#map");
  if (!mapElement || typeof L === "undefined") return;

  const lat = Number(document.body.dataset.lat);
  const lon = Number(document.body.dataset.lon);
  const map = L.map(mapElement, { zoomControl: true }).setView([lat, lon], 15);
  const slider = document.querySelector("#exposure-slider");
  const timeOutput = document.querySelector("#exposure-time");
  const statusLabel = document.querySelector("#exposure-status-label");
  const exposureStatus = document.querySelector("#exposure-status");
  const modeBadge = document.querySelector("#exposure-mode");
  const buildingsToggle = document.querySelector("#buildings-toggle");
  const whyPanel = document.querySelector("#why-panel");
  const compareButton = document.querySelector("#compare-hottest");
  const comparisonPanel = document.querySelector("#comparison-panel");
  let buildingLayer;
  let riskLayer;
  let selectedKeys = new Set();
  let riskRequestVersion = 0;
  let hasFittedBounds = false;

  // Tiles are optional: essential streets and interactions use cached API data.
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  const formatTime = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  const activeTime = () => formatTime(Number(slider?.value || 540));
  const riskColor = (riskClass) => ({ LOW: "#2e8b57", MODERATE: "#e2a132", HIGH: "#e76f34", CRITICAL: "#b42318" }[riskClass] || "#627d98");
  const append = (parent, tag, text, className) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    parent.append(element);
    return element;
  };
  const metric = (parent, label, value) => {
    const item = append(parent, "div", undefined, "metric");
    append(item, "dt", label);
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

  const renderWhy = (payload) => {
    if (!whyPanel) return;
    const { street } = payload;
    whyPanel.replaceChildren();
    append(whyPanel, "p", "Street explanation", "eyebrow");
    append(whyPanel, "h2", street.street_name || street.canonical_street_key);
    append(whyPanel, "p", `Street ID: ${street.canonical_street_key}`);
    const grid = append(whyPanel, "dl", undefined, "metric-grid");
    metric(grid, "Score / class", `${Number(street.risk_score).toFixed(1)} / ${street.risk_class}`);
    metric(grid, "Solar exposure", `${street.solar_exposure_level} (${Number(street.exposure_value).toFixed(2)})`);
    metric(grid, "Shade", `${street.shade_level} (${Number(street.shade_fraction).toFixed(2)})`);
    metric(grid, "Vulnerability", `${street.vulnerability_level} — estimated, density-based proxy`);
    metric(grid, "Cooling access", `${street.cooling_access_level} (${Number(street.access_penalty).toFixed(2)})`);
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
    } catch (error) {
      if (whyPanel) {
        whyPanel.replaceChildren();
        append(whyPanel, "h2", "Street explanation unavailable");
        append(whyPanel, "p", "The selected cached street explanation could not be loaded. Try another time or rerun the risk precompute step.", "panel-empty");
      }
      console.warn("HeatShield street explanation is unavailable.", error);
    }
  }

  const showRisk = async (requestedTime) => {
    const requestVersion = ++riskRequestVersion;
    if (exposureStatus) exposureStatus.textContent = `Loading cached modelled prioritization for ${requestedTime}...`;
    try {
      const response = await fetch(`/api/risk?time=${encodeURIComponent(requestedTime)}`);
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
    } catch (error) {
      if (exposureStatus) exposureStatus.textContent = "Risk cache is unavailable. Run `python scripts/precompute_risk.py`; cached base map data remains available.";
      console.warn("HeatShield risk data is unavailable.", error);
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
  slider?.addEventListener("input", () => showRisk(activeTime()));
  compareButton?.addEventListener("click", showComparison);
  loadBuildings();
  showRisk(activeTime());
})();
