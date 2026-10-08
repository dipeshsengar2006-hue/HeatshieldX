(() => {
  const mapElement = document.querySelector("#map");
  if (!mapElement || typeof L === "undefined") return;

  const lat = Number(document.body.dataset.lat);
  const lon = Number(document.body.dataset.lon);
  const map = L.map(mapElement, { zoomControl: true }).setView([lat, lon], 15);

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
})();
