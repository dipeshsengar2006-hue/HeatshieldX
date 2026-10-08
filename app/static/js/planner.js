(() => {
  const mapElement = document.querySelector("#map");
  if (!mapElement || typeof L === "undefined") return;

  const lat = Number(document.body.dataset.lat);
  const lon = Number(document.body.dataset.lon);
  const map = L.map(mapElement, { zoomControl: true }).setView([lat, lon], 15);
  let shadowLayer;
  let shadeLayer;

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

  const shadowStatus = document.querySelector("#shadow-status");
  const shadowButtons = document.querySelectorAll(".shadow-time");
  const shadeColor = (fraction) => {
    const red = Math.round(214 - (fraction * 110));
    const green = Math.round(69 + (fraction * 90));
    return `rgb(${red}, ${green}, 78)`;
  };

  const showShadowCheck = async (canonicalTime) => {
    if (shadowStatus) shadowStatus.textContent = `Loading cached shadows for ${canonicalTime}…`;
    try {
      const [shadowResponse, shadeResponse] = await Promise.all([
        fetch(`/api/shadows/${canonicalTime}/polygons`),
        fetch(`/api/shadows/${canonicalTime}/shade-fractions`),
      ]);
      if (!shadowResponse.ok || !shadeResponse.ok) throw new Error("Cached shadow data is unavailable.");
      const [shadowData, shadeData] = await Promise.all([shadowResponse.json(), shadeResponse.json()]);
      if (shadowLayer) map.removeLayer(shadowLayer);
      if (shadeLayer) map.removeLayer(shadeLayer);
      shadowLayer = L.geoJSON(shadowData, {
        style: { color: "#334e68", weight: 0.4, fillColor: "#334e68", fillOpacity: 0.18 },
      }).addTo(map);
      shadeLayer = L.geoJSON(shadeData, {
        style: (feature) => ({ color: shadeColor(feature.properties.shade_fraction), weight: 3.2, opacity: 0.9 }),
      }).addTo(map);
      shadowButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.shadowTime === canonicalTime)));
      const metadata = shadeData.metadata || {};
      const estimated = metadata.estimated_height_building_count || 0;
      if (shadowStatus) shadowStatus.textContent = `${canonicalTime}: geometric shadows loaded; ${estimated} building heights are estimated.`;
    } catch (error) {
      if (shadowStatus) shadowStatus.textContent = "Shadow cache is unavailable. Run `python scripts/precompute_shadows.py`; base streets and buildings remain available.";
      console.warn("HeatShield shadow validation data is unavailable.", error);
    }
  };

  shadowButtons.forEach((button) => {
    button.addEventListener("click", () => showShadowCheck(button.dataset.shadowTime));
  });
})();
