(() => {
  "use strict";

  const copy = JSON.parse(document.getElementById("citizen-strings").textContent);
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
    timeStatus.textContent = isCanonical ? copy.modelled : copy.interpolated;
    timeStatus.classList.toggle("estimated", !isCanonical);
  }
  range.addEventListener("input", setTimeLabel);
  setTimeLabel();

  function clearRouteDisplay() {
    routeLayers.splice(0).forEach((layer) => map.removeLayer(layer));
    stopMarkers.clearLayers();
    routeCards.replaceChildren();
    recommendation.hidden = true;
    recommendation.textContent = "";
    currentRoutes = [];
    selectedRoute = -1;
    stopList.replaceChildren(textNode("p", copy.stops_empty, "empty-state"));
  }

  function textNode(tag, content, className) {
    const node = document.createElement(tag);
    node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function format(value, key) {
    return copy[key].replace("{value}", value);
  }

  function routeLabel(routeType) {
    if (routeType === "FASTEST") return copy.card_fastest;
    if (routeType === "HEAT_AWARE") return copy.card_heat_aware;
    return copy.card_balanced;
  }

  function routeColor(routeType) {
    if (routeType === "HEAT_AWARE") return "#8a3ffc";
    if (routeType === "BALANCED") return "#a54817";
    return "#155e75";
  }

  function renderStops(route) {
    stopList.replaceChildren();
    const stops = route.stops || { status: "", items: [] };
    if (stops.status === "No stop data available") {
      stopList.append(textNode("p", copy.stops_unavailable, "empty-state"));
      return;
    }
    if (!stops.items || stops.items.length === 0) {
      stopList.append(textNode("p", copy.stops_no_eligible, "empty-state"));
      return;
    }
    const list = textNode("div", "", "stop-list");
    stops.items.forEach((stop) => {
      const item = textNode("article", "", "stop-item");
      const heading = textNode("h3", stop.name || copy.stop_type_other);
      const typeId = `stop_type_${stop.stop_type}`;
      const typeName = copy[typeId] || copy.stop_type_other;
      heading.append(document.createTextNode(` · ${typeName}`));
      if (stop.sponsored_status === true) {
        heading.append(textNode("span", copy.sponsored, "stop-sponsored"));
      }
      item.append(heading);
      item.append(textNode("p", `${copy.route_distance}: ${format(Math.round(stop.route_distance), "stop_distance_value")}`));
      item.append(textNode("p", `${copy.detour_distance}: ${format(Math.round(stop.detour_distance), "stop_distance_value")}`));
      item.append(textNode("p", copy.verified_status));
      if (Array.isArray(stop.amenities) && stop.amenities.length > 0) {
        item.append(textNode("p", `${copy.amenities}: ${stop.amenities.join(", ")}`));
      }
      item.append(textNode("p", copy.rating_unavailable));
      list.append(item);
      if (stop.location && Array.isArray(stop.location.coordinates)) {
        const [lon, lat] = stop.location.coordinates;
        L.circleMarker([lat, lon], {
          radius: 7,
          color: "#fff",
          weight: 2,
          fillColor: stopColor(stop.stop_type),
          fillOpacity: 1,
        }).bindTooltip(`${stop.name || copy.stop_type_other} · ${typeName}`).addTo(stopMarkers);
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
  }

  function renderRouteCard(route, index) {
    const card = textNode("button", "", "route-card");
    card.type = "button";
    card.dataset.route = route.route_type;
    card.setAttribute("aria-pressed", "false");
    const title = textNode("h3", routeLabel(route.route_type));
    card.append(title);
    const sameLabels = Array.isArray(route.same_as) ? route.same_as : [];
    if (sameLabels.length > 0) {
      const same = sameLabels.includes("FASTEST") || route.route_type === "FASTEST"
        ? copy.same_route_fastest
        : copy.same_as_route.replace("{route}", routeLabel(sameLabels[0]));
      card.append(textNode("span", same, "route-subtitle"));
    }
    if (route.route_type === "HEAT_AWARE") card.append(textNode("span", copy.route_heat_aware, "route-subtitle"));
    const metrics = document.createElement("dl");
    metrics.className = "route-metrics";
    const pairs = [
      [copy.time, format(Math.round(route.total_time_s / 60), "extra_minutes_value")],
      [copy.distance, format(Math.round(route.total_distance_m), "stop_distance_value")],
      [copy.modelled_heat, Number(route.modelled_heat_exposure).toFixed(1)],
      [copy.heat_change, `${Number(route.classification_vs_fastest.modelled_heat_exposure_change_percent).toFixed(1)}%`],
      [copy.extra_minutes, format(Math.max(0, Math.round(route.classification_vs_fastest.extra_minutes)), "extra_minutes_value")],
      [copy.weighted_shade, `${(Number(route.weighted_shade) * 100).toFixed(0)}%`],
      [copy.cooling_access, typeof route.cooling_access === "number" ? Number(route.cooling_access).toFixed(2) : copy.cooling_unavailable],
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
      routeCards.append(textNode("p", copy.empty_routes, "empty-state"));
      return;
    }
    recommendation.textContent = payload.recommendation || "";
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
  }

  function routeErrorMessage(status, detail) {
    const description = String(detail || "").toLowerCase();
    if (description.includes("outside") || description.includes("mapped area")) return copy.route_error_area;
    if (description.includes("path") || description.includes("connect")) return copy.route_error_path;
    if (status === 422) return copy.route_error_422;
    return copy.route_error_generic;
  }

  async function submitRoutes() {
    if (!fields.origin.point) {
      setStatus(copy.origin_required, true);
      fields.origin.input.focus();
      return;
    }
    if (!fields.destination.point) {
      setStatus(copy.destination_required, true);
      fields.destination.input.focus();
      return;
    }
    findButton.disabled = true;
    findButton.textContent = copy.finding_routes;
    setStatus(copy.status_loading_routes);
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
      if (!response.ok) throw new Error(routeErrorMessage(response.status, payload.detail));
      renderRoutes(payload);
      setStatus(copy.status_route_ready);
    } catch (error) {
      setStatus(error.message || copy.route_error_generic, true);
    } finally {
      findButton.disabled = false;
      findButton.textContent = copy.find_routes;
    }
  }

  document.getElementById("route-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitRoutes();
  });

  function showPlaceResults(field, places) {
    field.results.replaceChildren();
    if (!places.length) {
      field.results.append(textNode("p", copy.places_no_match, "empty-state"));
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
      });
      field.results.append(option);
    });
  }

  function attachAutocomplete(field) {
    let timer;
    field.input.addEventListener("input", () => {
      field.point = null;
      window.clearTimeout(timer);
      const query = field.input.value.trim();
      field.results.replaceChildren();
      if (query.length < 2) return;
      timer = window.setTimeout(async () => {
        field.results.append(textNode("p", copy.places_loading, "empty-state"));
        try {
          const response = await fetch(`${body.dataset.placesApi}?q=${encodeURIComponent(query)}`);
          if (!response.ok) throw new Error();
          const payload = await response.json();
          showPlaceResults(field, payload.places || []);
        } catch (_error) {
          field.results.replaceChildren(textNode("p", copy.places_error, "empty-state"));
        }
      }, 220);
    });
  }
  Object.values(fields).forEach(attachAutocomplete);

  document.getElementById("pick-origin").addEventListener("click", () => {
    activePick = "origin";
    setStatus(copy.map_pick_origin);
  });
  document.getElementById("pick-destination").addEventListener("click", () => {
    activePick = "destination";
    setStatus(copy.map_pick_destination);
  });
  map.on("click", (event) => {
    if (!activePick) return;
    const field = fields[activePick];
    field.point = { lat: event.latlng.lat, lon: event.latlng.lng };
    field.input.value = `${event.latlng.lat.toFixed(5)}, ${event.latlng.lng.toFixed(5)}`;
    field.results.replaceChildren();
    activePick = null;
    setStatus(copy.status_pick_required);
  });

  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      const preset = presets.find((item) => item.id === button.dataset.preset);
      if (!preset) return;
      fields.origin.point = preset.origin;
      fields.destination.point = preset.destination;
      fields.origin.input.value = copy[`preset_origin_${preset.id}`];
      fields.destination.input.value = preset.id === "riverside" ? copy.preset_destination_riverside : copy.preset_destination_mg;
      range.value = String(Number(preset.time.slice(0, 2)) * 60 + Number(preset.time.slice(3)));
      setTimeLabel();
      submitRoutes();
    });
  });

  fetch(body.dataset.streetsApi)
    .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
    .then((streets) => {
      streetLayer.addData(streets);
      if (streetLayer.getLayers().length) map.fitBounds(streetLayer.getBounds().pad(.08));
    })
    .catch(() => setStatus(copy.route_error_generic, true));
})();
