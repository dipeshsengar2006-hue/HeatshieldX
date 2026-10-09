(() => {
  "use strict";

  const catalogs = JSON.parse(document.getElementById("citizen-catalogs").textContent);
  const english = catalogs.en || {};
  let language = "en";
  try { language = localStorage.getItem("heatshield-citizen-language") === "hi" ? "hi" : "en"; } catch (_error) { /* Storage may be disabled. */ }
  let copy = catalogs[language] || english;
  const presets = JSON.parse(document.getElementById("citizen-presets").textContent);
  const body = document.body;
  const map = L.map("citizen-map", { scrollWheelZoom: false }).setView(
    [Number(body.dataset.lat), Number(body.dataset.lon)], 16
  );
  const tileNotice = document.getElementById("tile-notice");
  const tileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: copy.osm_attribution,
  });
  tileLayer.on("tileerror", () => { tileNotice.hidden = false; });
  tileLayer.addTo(map);

  const fields = {
    origin: { input: document.getElementById("origin-input"), results: document.getElementById("origin-results"), point: null },
    destination: { input: document.getElementById("destination-input"), results: document.getElementById("destination-results"), point: null },
  };
  const routeStatus = document.getElementById("route-status");
  const routeCards = document.getElementById("route-cards");
  const stopList = document.getElementById("stop-list");
  const recommendation = document.getElementById("recommendation");
  const findButton = document.getElementById("find-routes");
  const range = document.getElementById("departure-slider");
  const timeOutput = document.getElementById("departure-time");
  const timeStatus = document.getElementById("time-status");
  const streetLayer = L.geoJSON(null, { style: { color: "#586f7c", weight: 2, opacity: .72 } }).addTo(map);
  const routeLayers = [];
  const stopMarkers = L.layerGroup().addTo(map);
  let activePick = null;
  let currentRoutes = [];
  let selectedRoute = -1;
  let lastRoutePayload = null;
  let lastSummaryPayload = null;
  let summaryGeneration = 0;

  function updateCopilotContext() {
    if (!window.heatshieldCopilot) return;
    window.heatshieldCopilot.setContext({
      view: "citizen", time: timeOutput.value,
      origin: fields.origin.point || undefined, destination: fields.destination.point || undefined,
      origin_name: fields.origin.input.value.trim(), destination_name: fields.destination.input.value.trim(),
    });
  }

  function message(id, params = {}, englishFallback = "") {
    const template = (id && copy[id]) || (id && english[id]) || englishFallback || id || "";
    return String(template).replace(/\{([a-zA-Z0-9_]+)\}/g, (placeholder, name) => {
      return Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder;
    });
  }

  function backendMessage(payload, field, fallback = "") {
    if (!payload || typeof payload !== "object") return fallback;
    return message(payload[`${field}_message_id`], payload[`${field}_message_params`] || {}, payload[field] || fallback);
  }

  function applyLanguage() {
    copy = catalogs[language] || english;
    document.documentElement.lang = language;
    document.title = message("page_title");
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = message(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.placeholder = message(node.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
      node.setAttribute("aria-label", message(node.dataset.i18nAriaLabel));
    });
    document.querySelectorAll("[data-i18n-content]").forEach((node) => {
      node.content = message(node.dataset.i18nContent);
    });
    const footer = document.getElementById("citizen-footer");
    footer.textContent = message("footer", {
      config_version: footer.dataset.configVersion,
      data_download_date: footer.dataset.dataDate,
    });
    document.querySelectorAll("[data-language]").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.language === language ? "true" : "false");
    });
    window.heatshieldCopilot?.setLanguage(language);
    updateCopilotContext();
    setTimeLabel();
    if (lastSummaryPayload) renderSummary(lastSummaryPayload, Boolean(fields.origin.point));
    if (lastRoutePayload) renderRoutes(lastRoutePayload);
  }

  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      language = button.dataset.language === "hi" ? "hi" : "en";
      try { localStorage.setItem("heatshield-citizen-language", language); } catch (_error) { /* Storage may be disabled. */ }
      applyLanguage();
    });
  });

  function setStatus(message, isError = false) {
    routeStatus.textContent = message;
    routeStatus.classList.toggle("error", isError);
  }

  function setTimeLabel() {
    const minuteOfDay = Number(range.value);
    const hour = Math.floor(minuteOfDay / 60);
    const minute = minuteOfDay % 60;
    const time = `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
    timeOutput.value = time;
    timeOutput.textContent = time;
    const isCanonical = [540, 660, 780, 900, 1020].includes(minuteOfDay);
    timeStatus.textContent = message(isCanonical ? "modelled" : "interpolated");
    timeStatus.classList.toggle("estimated", !isCanonical);
    updateCopilotContext();
  }
  range.addEventListener("input", () => {
    setTimeLabel();
    invalidateRouteResults();
    refreshOriginSummary();
  });
  setTimeLabel();

  function clearRouteDisplay() {
    routeLayers.splice(0).forEach((layer) => map.removeLayer(layer));
    stopMarkers.clearLayers();
    routeCards.replaceChildren();
    recommendation.hidden = true;
    recommendation.textContent = "";
    currentRoutes = [];
    selectedRoute = -1;
    stopList.replaceChildren(textNode("p", message("stops_empty"), "empty-state"));
  }

  function textNode(tag, content, className) {
    const node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function format(value, key) {
    return message(key, { value });
  }

  function statusLabel(field) {
    return message(field && field.status_message_id, field && field.status_message_params || {}, field && field.status || "");
  }

  function renderSummary(payload, includeLocation) {
    lastSummaryPayload = payload;
    const peak = payload.peak_window || {};
    const peakText = message(peak.message_id, peak.message_params || {}, peak.english_text || "");
    document.getElementById("summary-peak").textContent = peakText;
    document.getElementById("summary-peak-status").textContent = statusLabel(peak);
    const locationFields = document.getElementById("summary-location-fields");
    locationFields.hidden = !includeLocation;
    if (includeLocation && payload.exposure_level) {
      const level = payload.exposure_level;
      const levelNode = document.getElementById("summary-level");
      levelNode.textContent = message(level.message_id, level.message_params || {}, level.english_text || level.value || "");
      levelNode.className = `summary-level level-${String(level.value || "").toLowerCase()}`;
      document.getElementById("summary-level-status").textContent = statusLabel(level);
      [
        ["water", payload.distance_to_water],
        ["cooling", payload.distance_to_cooling],
      ].forEach(([kind, field]) => {
        const valueNode = document.getElementById(`summary-${kind}`);
        valueNode.textContent = message(field && field.message_id, field && field.message_params || {}, field && field.english_text || "");
        document.getElementById(`summary-${kind}-status`).textContent = statusLabel(field);
      });
    }
    renderSummaryRouteNote(lastRoutePayload);
  }

  function hasQualifyingHeatRoute(payload) {
    if (!payload || !Array.isArray(payload.routes)) return false;
    if (payload.lower_exposure_route_available && payload.lower_exposure_route_available.value === true) return true;
    const threshold = Number(body.dataset.minHeatReductionPct || 5);
    return payload.routes.some((route) => route.route_type === "HEAT_AWARE"
      && Number(route.classification_vs_fastest && route.classification_vs_fastest.modelled_heat_exposure_change_percent) <= -threshold);
  }

  function renderSummaryRouteNote(payload) {
    const note = document.getElementById("summary-route-note");
    if (!hasQualifyingHeatRoute(payload)) {
      note.hidden = true;
      note.textContent = "";
      return;
    }
    const summaryRoute = payload.lower_exposure_route_available;
    const routeText = summaryRoute
      ? message(summaryRoute.message_id, summaryRoute.message_params || {}, summaryRoute.english_text || "")
      : message("summary_lower_route");
    const routeStatus = summaryRoute ? statusLabel(summaryRoute) : message("summary_status_modelled");
    note.textContent = `${routeText} (${routeStatus})`;
    note.hidden = false;
  }

  async function refreshSummary(point, includeLocation) {
    const generation = ++summaryGeneration;
    const status = document.getElementById("summary-status");
    status.textContent = message("summary_loading");
    try {
      const response = await fetch(body.dataset.summaryApi, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat: point.lat, lon: point.lon, time: timeOutput.value }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(message(payload.message_id, payload.message_params || {}, payload.detail || message("summary_error")));
      if (generation !== summaryGeneration) return;
      renderSummary(payload, includeLocation);
      status.textContent = "";
    } catch (error) {
      if (generation !== summaryGeneration) return;
      lastSummaryPayload = null;
      document.getElementById("summary-location-fields").hidden = true;
      status.textContent = error.message || message("summary_error");
    }
  }

  function invalidateRouteResults() {
    lastRoutePayload = null;
    renderSummaryRouteNote(null);
    clearRouteDisplay();
  }

  async function refreshOriginSummary() {
    if (fields.origin.point) await refreshSummary(fields.origin.point, true);
    else {
      lastRoutePayload = null;
      renderSummaryRouteNote(null);
      refreshSummary({ lat: Number(body.dataset.lat), lon: Number(body.dataset.lon) }, false);
    }
  }

  function routeLabel(routeType) {
    const ids = { FASTEST: "card_fastest", HEAT_AWARE: "card_heat_aware", BALANCED: "card_balanced" };
    return message(ids[routeType] || "card_fastest");
  }

  function routeColor(routeType) {
    if (routeType === "HEAT_AWARE") return "#8a3ffc";
    if (routeType === "BALANCED") return "#a54817";
    return "#155e75";
  }

  function renderStops(route) {
    stopList.replaceChildren();
    const stops = route.stops || { status: "", items: [] };
    if ((stops.status_message_id || "") === "stops_unavailable" || stops.status === "No stop data available") {
      stopList.append(textNode("p", message(stops.status_message_id || "stops_unavailable", stops.status_message_params || {}, stops.status), "empty-state"));
      return;
    }
    if (!stops.items || stops.items.length === 0) {
      stopList.append(textNode("p", message(stops.status_message_id || "stops_no_eligible", stops.status_message_params || {}, stops.status || copy.stops_no_eligible), "empty-state"));
      return;
    }
    const list = textNode("div", "", "stop-list");
    stops.items.forEach((stop) => {
      const item = textNode("article", "", "stop-item");
      const heading = textNode("h3", stop.name || message("stop_type_other"));
      const typeId = stop.stop_type_message_id || `stop_type_${stop.stop_type}`;
      const typeName = message(typeId, stop.stop_type_message_params || {}, stop.stop_type || copy.stop_type_other);
      heading.append(document.createTextNode(` · ${typeName}`));
      if (stop.sponsored_status === true) {
        heading.append(textNode("span", message("sponsored"), "stop-sponsored"));
      }
      item.append(heading);
      item.append(textNode("p", `${message("route_distance")}: ${format(Math.round(stop.route_distance), "stop_distance_value")}`));
      item.append(textNode("p", `${message("detour_distance")}: ${format(Math.round(stop.detour_distance), "stop_distance_value")}`));
      item.append(textNode("p", message(stop.verified_status_message_id || "verified_status", stop.verified_status_message_params || {}, stop.verified_status || message("verified_status"))));
      if (Array.isArray(stop.amenities) && stop.amenities.length > 0) {
        item.append(textNode("p", `${message("amenities")}: ${stop.amenities.join(", ")}`));
      }
      item.append(textNode("p", message(stop.rating_message_id || "rating_unavailable", stop.rating_message_params || {}, stop.rating_label || message("rating_unavailable"))));
      list.append(item);
      if (stop.location && Array.isArray(stop.location.coordinates)) {
        const [lon, lat] = stop.location.coordinates;
        L.circleMarker([lat, lon], {
          radius: 7,
          color: "#fff",
          weight: 2,
          fillColor: stopColor(stop.stop_type),
          fillOpacity: 1,
        }).bindTooltip(`${stop.name || message("stop_type_other")} · ${typeName}`).addTo(stopMarkers);
      }
    });
    stopList.append(list);
  }

  function stopColor(type) {
    return ({ water: "#087e8b", cooling: "#4d7c0f", shaded_public: "#665191", business: "#9a6700" })[type] || "#475569";
  }

  function selectRoute(index) {
    selectedRoute = index;
    routeCards.querySelectorAll(".route-card").forEach((card, cardIndex) => {
      card.setAttribute("aria-pressed", cardIndex === index ? "true" : "false");
    });
    routeLayers.forEach((layer, layerIndex) => {
      const route = currentRoutes[layerIndex];
      layer.setStyle({
        weight: layerIndex === index ? 8 : 5,
        opacity: layerIndex === index ? 1 : .78,
        color: routeColor(route.route_type),
      });
      if (layerIndex === index) layer.bringToFront();
    });
    renderStops(currentRoutes[index]);
    updateCopilotContext();
  }

  function renderRouteCard(route, index) {
    const card = textNode("button", "", "route-card");
    card.type = "button";
    card.dataset.route = route.route_type;
    card.setAttribute("aria-pressed", "false");
    const title = textNode("h3", message(route.route_type_message_id, route.route_type_message_params || {}, routeLabel(route.route_type)));
    card.append(title);
    const sameLabels = Array.isArray(route.same_as_messages) ? route.same_as_messages : [];
    if (sameLabels.length > 0) {
      sameLabels.forEach((same) => card.append(textNode("span", message(same.message_id, same.message_params || {}, same.text || copy.same_route_fastest), "route-subtitle")));
    }
    if (route.route_type === "HEAT_AWARE") card.append(textNode("span", message("route_heat_aware"), "route-subtitle"));
    const metrics = document.createElement("dl");
    metrics.className = "route-metrics";
    const pairs = [
      [message("time"), format(Math.round(route.total_time_s / 60), "extra_minutes_value")],
      [message("distance"), format(Math.round(route.total_distance_m), "stop_distance_value")],
      [message("modelled_heat"), Number(route.modelled_heat_exposure).toFixed(1)],
      [message("heat_change"), `${Number(route.classification_vs_fastest.modelled_heat_exposure_change_percent).toFixed(1)}%`],
      [message("extra_minutes"), format(Math.max(0, Math.round(route.classification_vs_fastest.extra_minutes)), "extra_minutes_value")],
      [message("weighted_shade"), `${(Number(route.weighted_shade) * 100).toFixed(0)}%`],
      [message(route.cooling_access_message_id || "cooling_access"), typeof route.cooling_access === "number" ? Number(route.cooling_access).toFixed(2) : message(route.cooling_access_message_id || "cooling_unavailable", route.cooling_access_message_params || {}, route.cooling_access)],
    ];
    pairs.forEach(([label, value]) => {
      const wrapper = document.createElement("div");
      wrapper.append(textNode("dt", label), textNode("dd", value));
      metrics.append(wrapper);
    });
    card.append(metrics);
    card.addEventListener("click", () => selectRoute(index));
    return card;
  }

  function renderRoutes(payload) {
    clearRouteDisplay();
    currentRoutes = payload.routes || [];
    if (!currentRoutes.length) {
      routeCards.append(textNode("p", message("empty_routes"), "empty-state"));
      return;
    }
    recommendation.textContent = message(payload.recommendation_message_id, payload.recommendation_message_params || {}, payload.recommendation || "");
    recommendation.hidden = !payload.recommendation;
    currentRoutes.forEach((route, index) => {
      routeCards.append(renderRouteCard(route, index));
      const layer = L.geoJSON(route.geometry, {
        style: { color: routeColor(route.route_type), weight: 5, opacity: .78 },
        interactive: true,
      }).addTo(map);
      layer.on("click", () => selectRoute(index));
      routeLayers.push(layer);
    });
    const allCoordinates = routeLayers.flatMap((layer) => layer.getLayers().flatMap((line) => line.getLatLngs()));
    if (allCoordinates.length) map.fitBounds(L.latLngBounds(allCoordinates).pad(.12), { maxZoom: 18 });
    selectRoute(0);
    renderSummaryRouteNote(payload);
    updateCopilotContext();
  }

  function routeErrorMessage(status, detail, errorPayload = {}) {
    if (errorPayload.message_id) return message(errorPayload.message_id, errorPayload.message_params || {}, detail || "");
    const description = String(detail || "").toLowerCase();
    if (description.includes("outside") || description.includes("mapped area")) return message("route_error_area");
    if (description.includes("path") || description.includes("connect")) return message("route_error_path");
    if (status === 422) return message("route_error_422");
    return message("route_error_generic");
  }

  async function submitRoutes() {
    if (!fields.origin.point) {
      setStatus(message("origin_required"), true);
      fields.origin.input.focus();
      return;
    }
    if (!fields.destination.point) {
      setStatus(message("destination_required"), true);
      fields.destination.input.focus();
      return;
    }
    findButton.disabled = true;
    findButton.textContent = message("finding_routes");
    setStatus(message("status_loading_routes"));
    lastRoutePayload = null;
    renderSummaryRouteNote(null);
    clearRouteDisplay();
    try {
      const response = await fetch(body.dataset.routeApi, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin: fields.origin.point,
          destination: fields.destination.point,
          time: timeOutput.value,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(routeErrorMessage(response.status, payload.detail, payload));
      lastRoutePayload = payload;
      renderRoutes(payload);
      setStatus(message("status_route_ready"));
    } catch (error) {
      setStatus(error.message || message("route_error_generic"), true);
    } finally {
      findButton.disabled = false;
      findButton.textContent = message("find_routes");
    }
  }

  document.getElementById("route-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitRoutes();
  });

  function showPlaceResults(field, places) {
    field.results.replaceChildren();
    if (!places.length) {
      field.results.append(textNode("p", message("places_no_match"), "empty-state"));
      return;
    }
    places.forEach((place) => {
      const option = textNode("button", place.name, "place-result");
      option.type = "button";
      option.setAttribute("role", "option");
      option.addEventListener("click", () => {
        field.point = { lat: place.location.coordinates[1], lon: place.location.coordinates[0] };
        field.input.value = place.name;
        field.results.replaceChildren();
        invalidateRouteResults();
        if (field === fields.origin) refreshOriginSummary();
        updateCopilotContext();
      });
      field.results.append(option);
    });
  }

  function attachAutocomplete(field) {
    let timer;
    let originSummaryTimer;
    field.input.addEventListener("input", () => {
      field.point = null;
      updateCopilotContext();
      window.clearTimeout(timer);
      if (field === fields.origin) {
        window.clearTimeout(originSummaryTimer);
        invalidateRouteResults();
        originSummaryTimer = window.setTimeout(refreshOriginSummary, 350);
      } else {
        invalidateRouteResults();
      }
      const query = field.input.value.trim();
      field.results.replaceChildren();
      if (query.length < 2) return;
      timer = window.setTimeout(async () => {
        field.results.append(textNode("p", message("places_loading"), "empty-state"));
        try {
          const response = await fetch(`${body.dataset.placesApi}?q=${encodeURIComponent(query)}`);
          if (!response.ok) throw new Error();
          const payload = await response.json();
          showPlaceResults(field, payload.places || []);
        } catch (_error) {
          field.results.replaceChildren(textNode("p", message("places_error"), "empty-state"));
        }
      }, 220);
    });
  }
  Object.values(fields).forEach(attachAutocomplete);

  document.getElementById("pick-origin").addEventListener("click", () => {
    activePick = "origin";
    setStatus(message("map_pick_origin"));
  });
  document.getElementById("pick-destination").addEventListener("click", () => {
    activePick = "destination";
    setStatus(message("map_pick_destination"));
  });
  map.on("click", (event) => {
    if (!activePick) return;
    const field = fields[activePick];
    field.point = { lat: event.latlng.lat, lon: event.latlng.lng };
    field.input.value = `${event.latlng.lat.toFixed(5)}, ${event.latlng.lng.toFixed(5)}`;
    field.results.replaceChildren();
    activePick = null;
    invalidateRouteResults();
    setStatus(message("status_pick_required"));
    if (field === fields.origin) refreshOriginSummary();
    updateCopilotContext();
  });

  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      const preset = presets.find((item) => item.id === button.dataset.preset);
      if (!preset) return;
      fields.origin.point = preset.origin;
      fields.destination.point = preset.destination;
      fields.origin.input.value = copy[`preset_origin_${preset.id}`];
      fields.destination.input.value = preset.id === "riverside" ? copy.preset_destination_riverside : copy.preset_destination_mg;
      invalidateRouteResults();
      range.value = String(Number(preset.time.slice(0, 2)) * 60 + Number(preset.time.slice(3)));
      setTimeLabel();
      updateCopilotContext();
      refreshOriginSummary();
      submitRoutes();
    });
  });

  fetch(body.dataset.streetsApi)
    .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
    .then((streets) => {
      streetLayer.addData(streets);
      if (streetLayer.getLayers().length) map.fitBounds(streetLayer.getBounds().pad(.08));
    })
    .catch(() => setStatus(message("route_error_generic"), true));

  applyLanguage();
  refreshSummary({ lat: Number(body.dataset.lat), lon: Number(body.dataset.lon) }, false);
})();
