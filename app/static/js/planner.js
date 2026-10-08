(() => {
  const mapElement = document.querySelector("#map");
  if (!mapElement || typeof L === "undefined") return;

  const lat = Number(document.body.dataset.lat);
  const lon = Number(document.body.dataset.lon);
  const map = L.map(mapElement, { zoomControl: true }).setView([lat, lon], 15);
  let exposureLayer;

  // Tiles are optional presentation assets. Cached application data remains usable without them.
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  const addLayer = async (url, style) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Could not load ${url}`);
    const collection = await response.json();
    return L.geoJSON(collection, { style });
  };

  Promise.all([
    addLayer("/api/street-segments", { color: "#d64523", weight: 2.4, opacity: 0.85 }),
    addLayer("/api/buildings", { color: "#657483", weight: 1, fillColor: "#7d8a97", fillOpacity: 0.35 }),
  ]).then((layers) => {
    const group = L.featureGroup(layers).addTo(map);
    if (group.getBounds().isValid()) map.fitBounds(group.getBounds(), { padding: [24, 24] });
  }).catch((error) => console.warn("HeatShield map data is unavailable.", error));

  const slider = document.querySelector("#exposure-slider");
  const timeOutput = document.querySelector("#exposure-time");
  const statusLabel = document.querySelector("#exposure-status-label");
  const exposureStatus = document.querySelector("#exposure-status");
  const modeBadge = document.querySelector("#exposure-mode");
  const formatTime = (minutes) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
  const exposureColor = (value) => {
    const red = Math.round(72 + (value * 166));
    const green = Math.round(141 - (value * 82));
    return `rgb(${red}, ${green}, 64)`;
  };

  const showExposure = async (requestedTime) => {
    if (exposureStatus) exposureStatus.textContent = `Loading cached exposure for ${requestedTime}...`;
    try {
      const response = await fetch(`/api/exposure?time=${encodeURIComponent(requestedTime)}`);
      if (!response.ok) throw new Error("Cached exposure data is unavailable.");
      const collection = await response.json();
      if (exposureLayer) map.removeLayer(exposureLayer);
      exposureLayer = L.geoJSON(collection, {
        style: (feature) => ({ color: exposureColor(feature.properties.exposure_value), weight: 3.5, opacity: 0.92 }),
      }).addTo(map);
      const metadata = collection.metadata || {};
      const interpolated = Boolean(metadata.interpolated);
      if (timeOutput) timeOutput.textContent = requestedTime;
      if (statusLabel) statusLabel.textContent = interpolated ? "Interpolated / Estimated" : "Modelled";
      if (modeBadge) {
        const geometric = metadata.computation_mode === "geometric";
        modeBadge.textContent = geometric ? "Geometric shadow mode" : "Estimated Exposure Mode";
        modeBadge.dataset.mode = geometric ? "geometric" : "estimated";
      }
      if (exposureStatus) exposureStatus.textContent = interpolated
        ? `${requestedTime} is linearly interpolated from cached ${metadata.interpolation_lower_time} and ${metadata.interpolation_upper_time} snapshots.`
        : `${requestedTime} uses a cached ${metadata.computation_mode} exposure snapshot.`;
    } catch (error) {
      if (exposureStatus) exposureStatus.textContent = "Exposure cache is unavailable. Run `python scripts/precompute_exposure.py`; base streets and buildings remain available.";
      console.warn("HeatShield exposure data is unavailable.", error);
    }
  };

  if (slider) {
    slider.addEventListener("input", () => showExposure(formatTime(Number(slider.value))));
    showExposure(formatTime(Number(slider.value)));
  }
})();
