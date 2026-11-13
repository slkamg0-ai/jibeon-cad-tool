// State
let currentSessionId = null;
let currentLayers = []; // array of layer summary objects
let selectedLayerKeys = new Set();
let presets = {};
let map = null;
let vectorLayerGroup = null;
let labelLayerGroup = null;
let baseLayers = {};
let currentExportFormat = "dxf";
let previewDebounceTimer = null;

// DOM Elements
const jibeonAddressInput = document.getElementById("jibeon-address-input");
const btnFetchJibeon = document.getElementById("btn-fetch-jibeon");
const jibeonBufferSelect = document.getElementById("jibeon-buffer-select");
const jibeonBufferCustom = document.getElementById("jibeon-buffer-custom");
const jibeonShapeSelect = document.getElementById("jibeon-shape-select");

function getBufferMeters() {
  if (jibeonBufferSelect && jibeonBufferSelect.value === "custom") {
    const val = parseFloat(jibeonBufferCustom ? jibeonBufferCustom.value : "");
    if (!isNaN(val) && val > 0) return Math.min(Math.max(val, 10), 3000);
    return 1000;
  }
  return parseFloat(jibeonBufferSelect ? jibeonBufferSelect.value : "100") || 100;
}
const jibeonStatusBadge = document.getElementById("jibeon-status-badge");
const jibeonInfoCard = document.getElementById("jibeon-info-card");
const jibeonTargetName = document.getElementById("jibeon-target-name");
const jibeonPnuText = document.getElementById("jibeon-pnu-text");
const jibeonAreaText = document.getElementById("jibeon-area-text");
const distanceAlertBox = document.getElementById("distance-alert-box");
const distanceAlertTitle = document.getElementById("distance-alert-title");
const distanceAlertDesc = document.getElementById("distance-alert-desc");
const btnFixToTopoCenter = document.getElementById("btn-fix-to-topo-center");
const topoDetectedAddr = document.getElementById("topo-detected-addr");
const btnSyncTopoCadastral = document.getElementById("btn-sync-topo-cadastral");
const clipToBorderCheckbox = document.getElementById("clip-to-border-checkbox");
const dxfElementsCheckbox = document.getElementById("dxf-elements-checkbox");
const dxfBylayerCheckbox = document.getElementById("dxf-bylayer-checkbox");
const btnSaveCustomPreset = document.getElementById("btn-save-custom-preset");
const customPresetsContainer = document.getElementById("custom-presets-container");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const fileInfoCard = document.getElementById("file-info-card");
const fileNameEl = document.getElementById("file-name");
const fileCrsBadge = document.getElementById("file-crs-badge");
const layerCountInfo = document.getElementById("layer-count-info");
const featCountInfo = document.getElementById("feat-count-info");
const uploadStatusBadge = document.getElementById("upload-status-badge");
const layerTreeContainer = document.getElementById("layer-tree-container");
const selectedSummaryBadge = document.getElementById("selected-summary-badge");
const layerSearchInput = document.getElementById("layer-search-input");
const exportCrsSelect = document.getElementById("export-crs-select");
const btnExportMap = document.getElementById("btn-export-map");
const btnFitBounds = document.getElementById("btn-fit-bounds");
const baseLayerSelect = document.getElementById("base-layer-select");
const loadingOverlay = document.getElementById("loading-overlay");
const loadingText = document.getElementById("loading-text");
const btnLoadSample = document.getElementById("btn-load-sample");
const btnHeaderCombineTopo = document.getElementById("btn-header-combine-topo");
const btnCardCombineTopo = document.getElementById("btn-card-combine-topo");
const btnSelectAll = document.getElementById("btn-select-all");
const btnDeselectAll = document.getElementById("btn-deselect-all");
const elevationStatsPill = document.getElementById("elevation-stats-pill");
const statElevRange = document.getElementById("stat-elev-range");
const statVisibleFeatures = document.getElementById("stat-visible-features");

// Mobile UI Elements
const sidebarPanel = document.getElementById("sidebar-panel");
const btnMobileToggleDrawer = document.getElementById("btn-mobile-toggle-drawer");
const toggleDrawerIcon = document.getElementById("toggle-drawer-icon");
const toggleDrawerLabel = document.getElementById("toggle-drawer-label");
const btnCloseDrawer = document.getElementById("btn-close-drawer");
const mobileBottomNav = document.getElementById("mobile-bottom-nav");
const mobileQuickAddress = document.getElementById("mobile-quick-address");
const btnMobileQuickSearch = document.getElementById("btn-mobile-quick-search");
const btnMobileClearAddr = document.getElementById("btn-mobile-clear-addr");

// Initialize Leaflet Map
function initMap() {
  map = L.map('map', {
    zoomControl: true,
    attributionControl: true
  }).setView([37.0313, 127.0302], 15);

  baseLayers.osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
  });

  baseLayers.vworld_base = L.tileLayer('https://xdworld.vworld.kr/2d/Base/service/{z}/{x}/{y}.png', {
    attribution: '&copy; 국토지리정보원 VWorld',
    maxZoom: 19
  });

  baseLayers.vworld_sat = L.layerGroup([
    L.tileLayer('https://xdworld.vworld.kr/2d/Satellite/service/{z}/{x}/{y}.jpeg', { maxZoom: 19 }),
    L.tileLayer('https://xdworld.vworld.kr/2d/Hybrid/service/{z}/{x}/{y}.png', { maxZoom: 19 })
  ]);

  baseLayers.carto_dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CARTO',
    maxZoom: 19
  });

  // Default to VWorld Satellite
  baseLayers.vworld_sat.addTo(map);

  vectorLayerGroup = L.featureGroup().addTo(map);
  labelLayerGroup = L.featureGroup().addTo(map);

  baseLayerSelect.addEventListener('change', (e) => {
    Object.values(baseLayers).forEach(layer => map.removeLayer(layer));
    const selected = baseLayers[e.target.value] || baseLayers.vworld_sat;
    selected.addTo(map);
  });

  btnFitBounds.addEventListener('click', () => {
    if (vectorLayerGroup && vectorLayerGroup.getLayers().length > 0) {
      map.fitBounds(vectorLayerGroup.getBounds(), { padding: [40, 40] });
    }
  });
}

const MAJOR_COLORS = {
  "교통": "bg-slate-750 text-slate-300 border-slate-650",
  "건물": "bg-slate-750 text-slate-200 border-slate-650",
  "시설": "bg-slate-750 text-slate-300 border-slate-650",
  "식생": "bg-slate-800 text-slate-400 border-slate-700",
  "수계": "bg-slate-750 text-slate-300 border-slate-650",
  "지형": "bg-slate-750 text-slate-300 border-slate-650",
  "경계": "bg-slate-750 text-slate-200 border-slate-650",
  "주기": "bg-slate-800 text-slate-400 border-slate-700",
  "기타": "bg-slate-800 text-slate-400 border-slate-700"
};

function showLoading(text) {
  loadingText.textContent = text || "처리 중...";
  loadingOverlay.classList.remove("hidden");
}
function hideLoading() {
  loadingOverlay.classList.add("hidden");
}

// Render 3-Tier Layer Tree in DOM
function renderLayerTree(filterText = "") {
  layerTreeContainer.innerHTML = "";
  const filter = filterText.trim().toLowerCase();

  // 1. Render Dedicated Cadastral Card if cadastral layers exist
  const cadastralKeys = ["HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"];
  const cadastralLayers = currentLayers.filter(l => cadastralKeys.includes(l.layer_name));
  const topoLayers = currentLayers.filter(l => !cadastralKeys.includes(l.layer_name));

  if (cadastralLayers.length > 0) {
    const cadCard = document.createElement("div");
    cadCard.className = "bg-rose-950/30 border border-rose-800/60 rounded-xl overflow-hidden shadow-sm mb-3";

    const cadHeader = document.createElement("div");
    cadHeader.className = "px-3 py-2.5 bg-rose-900/40 flex items-center justify-between select-none border-b border-rose-800/40";

    const cadLeft = document.createElement("div");
    cadLeft.className = "flex items-center gap-2";

    const cadMasterCheck = document.createElement("input");
    cadMasterCheck.type = "checkbox";
    cadMasterCheck.className = "rounded border-rose-600 text-rose-500 focus:ring-0 cursor-pointer";
    const cadSelectedCount = cadastralLayers.filter(it => selectedLayerKeys.has(it.layer_name)).length;
    cadMasterCheck.checked = (cadSelectedCount === cadastralLayers.length && cadastralLayers.length > 0);
    cadMasterCheck.indeterminate = (cadSelectedCount > 0 && cadSelectedCount < cadastralLayers.length);

    const cadTitle = document.createElement("span");
    cadTitle.className = "font-bold text-xs text-rose-200 flex items-center gap-1.5";
    cadTitle.innerHTML = `<i class="ph-bold ph-map-pin text-rose-400"></i> VWorld 실시간 지적도 레이어 <span class="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-300 font-mono">캐드 필수</span>`;

    cadLeft.appendChild(cadMasterCheck);
    cadLeft.appendChild(cadTitle);

    const cadRight = document.createElement("div");
    cadRight.className = "text-[11px] text-rose-300 font-mono";
    cadRight.textContent = `${cadSelectedCount}/${cadastralLayers.length}`;

    cadHeader.appendChild(cadLeft);
    cadHeader.appendChild(cadRight);
    cadCard.appendChild(cadHeader);

    const cadBody = document.createElement("div");
    cadBody.className = "p-2 space-y-1 bg-slate-900/40";

    cadastralLayers.forEach(it => {
      const row = document.createElement("div");
      row.className = "flex items-center justify-between text-xs py-1 px-2 rounded hover:bg-rose-900/20 transition";

      const left = document.createElement("div");
      left.className = "flex items-center gap-2";

      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.className = "rounded border-rose-600 text-rose-500 focus:ring-0 cursor-pointer";
      chk.checked = selectedLayerKeys.has(it.layer_name);

      const colorDot = document.createElement("span");
      colorDot.className = "w-2.5 h-2.5 rounded-full shrink-0 border border-black/30";
      colorDot.style.backgroundColor = it.style?.color || "#EF4444";

      const lbl = document.createElement("span");
      lbl.className = "text-[11px] text-slate-200 font-medium";
      lbl.textContent = it.minor || it.layer_name;

      left.appendChild(chk);
      left.appendChild(colorDot);
      left.appendChild(lbl);

      const cnt = document.createElement("span");
      cnt.className = "text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-rose-300 font-mono";
      cnt.textContent = `${it.feature_count}개`;

      row.appendChild(left);
      row.appendChild(cnt);
      cadBody.appendChild(row);

      chk.addEventListener("change", () => {
        if (chk.checked) selectedLayerKeys.add(it.layer_name);
        else selectedLayerKeys.delete(it.layer_name);
        renderLayerTree(layerSearchInput.value);
        triggerPreviewUpdate();
      });
    });

    cadMasterCheck.addEventListener("change", (e) => {
      e.stopPropagation();
      cadastralLayers.forEach(it => {
        if (cadMasterCheck.checked) selectedLayerKeys.add(it.layer_name);
        else selectedLayerKeys.delete(it.layer_name);
      });
      renderLayerTree(layerSearchInput.value);
      triggerPreviewUpdate();
    });

    cadCard.appendChild(cadBody);
    layerTreeContainer.appendChild(cadCard);
  }

  // 2. Render Topographic Layers by Category
  const tree = {};
  topoLayers.forEach(l => {
    const maj = l.major || "기타";
    const mid = l.mid || "기타";
    if (!tree[maj]) tree[maj] = {};
    if (!tree[maj][mid]) tree[maj][mid] = [];
    tree[maj][mid].push(l);
  });

  Object.keys(tree).sort().forEach(maj => {
    const mids = tree[maj];
    
    let majHasVisible = false;
    Object.keys(mids).forEach(mid => {
      const matched = mids[mid].filter(it => 
        !filter || 
        it.code.toLowerCase().includes(filter) || 
        it.minor.toLowerCase().includes(filter) ||
        mid.toLowerCase().includes(filter) ||
        maj.toLowerCase().includes(filter)
      );
      if (matched.length > 0) majHasVisible = true;
    });

    if (!majHasVisible) return;

    const majCard = document.createElement("div");
    majCard.className = "bg-slate-750/70 border border-slate-650 rounded-xl overflow-hidden";

    const majHeader = document.createElement("div");
    majHeader.className = "px-3 py-2 bg-slate-750 flex items-center justify-between cursor-pointer select-none hover:bg-slate-700 transition";
    
    const majLeft = document.createElement("div");
    majLeft.className = "flex items-center gap-2";

    const majCheckbox = document.createElement("input");
    majCheckbox.type = "checkbox";
    majCheckbox.className = "rounded border-slate-600 text-indigo-500 focus:ring-0 cursor-pointer";
    
    const majBadgeClass = MAJOR_COLORS[maj] || MAJOR_COLORS["기타"];
    const majTitle = document.createElement("span");
    majTitle.className = "font-bold text-xs text-slate-100 flex items-center gap-1.5";
    majTitle.innerHTML = `<span class="badge-major border ${majBadgeClass}">${maj}</span>`;

    majLeft.appendChild(majCheckbox);
    majLeft.appendChild(majTitle);

    const majRight = document.createElement("div");
    majRight.className = "flex items-center gap-2 text-[11px] text-slate-400";
    const majCountBadge = document.createElement("span");
    
    let allMajLayerKeys = [];
    Object.values(mids).forEach(arr => arr.forEach(x => allMajLayerKeys.push(x.layer_name)));
    const majSelectedCount = allMajLayerKeys.filter(k => selectedLayerKeys.has(k)).length;
    majCountBadge.textContent = `${majSelectedCount}/${allMajLayerKeys.length}`;
    
    majCheckbox.checked = (majSelectedCount === allMajLayerKeys.length && allMajLayerKeys.length > 0);
    majCheckbox.indeterminate = (majSelectedCount > 0 && majSelectedCount < allMajLayerKeys.length);

    majRight.appendChild(majCountBadge);
    const chevronIcon = document.createElement("i");
    chevronIcon.className = "ph ph-caret-down text-slate-400 transition-transform";
    majRight.appendChild(chevronIcon);

    majHeader.appendChild(majLeft);
    majHeader.appendChild(majRight);
    majCard.appendChild(majHeader);

    const majBody = document.createElement("div");
    majBody.className = "p-2.5 space-y-2 border-t border-slate-650/50";

    majCheckbox.addEventListener("change", (e) => {
      e.stopPropagation();
      allMajLayerKeys.forEach(k => {
        if (majCheckbox.checked) selectedLayerKeys.add(k);
        else selectedLayerKeys.delete(k);
      });
      renderLayerTree(layerSearchInput.value);
      triggerPreviewUpdate();
    });

    majHeader.addEventListener("click", (e) => {
      if (e.target === majCheckbox) return;
      majBody.classList.toggle("hidden");
      chevronIcon.classList.toggle("rotate-180");
    });

    Object.keys(mids).sort().forEach(mid => {
      const items = mids[mid].filter(it => 
        !filter || 
        it.code.toLowerCase().includes(filter) || 
        it.minor.toLowerCase().includes(filter) ||
        mid.toLowerCase().includes(filter) ||
        maj.toLowerCase().includes(filter)
      );

      if (items.length === 0) return;

      const midBox = document.createElement("div");
      midBox.className = "bg-slate-800/80 rounded-lg p-2 border border-slate-700/80 space-y-1.5";

      const midHeader = document.createElement("div");
      midHeader.className = "flex items-center justify-between text-xs";
      
      const midLeft = document.createElement("div");
      midLeft.className = "flex items-center gap-1.5";
      const midCheckbox = document.createElement("input");
      midCheckbox.type = "checkbox";
      midCheckbox.className = "rounded border-slate-600 text-indigo-500 focus:ring-0 cursor-pointer";
      
      const midTitle = document.createElement("span");
      midTitle.className = "font-medium text-slate-200 text-xs";
      midTitle.textContent = mid;

      midLeft.appendChild(midCheckbox);
      midLeft.appendChild(midTitle);

      const midKeys = items.map(x => x.layer_name);
      const midSelectedCount = midKeys.filter(k => selectedLayerKeys.has(k)).length;
      midCheckbox.checked = (midSelectedCount === midKeys.length && midKeys.length > 0);
      midCheckbox.indeterminate = (midSelectedCount > 0 && midSelectedCount < midKeys.length);

      const midCountSpan = document.createElement("span");
      midCountSpan.className = "text-[10px] text-slate-400";
      midCountSpan.textContent = `${items.length}종`;

      midHeader.appendChild(midLeft);
      midHeader.appendChild(midCountSpan);
      midBox.appendChild(midHeader);

      midCheckbox.addEventListener("change", () => {
        midKeys.forEach(k => {
          if (midCheckbox.checked) selectedLayerKeys.add(k);
          else selectedLayerKeys.delete(k);
        });
        renderLayerTree(layerSearchInput.value);
        triggerPreviewUpdate();
      });

      const itemsContainer = document.createElement("div");
      itemsContainer.className = "pl-4 space-y-1 border-l border-slate-700/60";

      items.forEach(it => {
        const itemRow = document.createElement("div");
        itemRow.className = "flex items-center justify-between text-xs py-1 px-1.5 rounded hover:bg-slate-700/40 transition group";

        const itemLeft = document.createElement("div");
        itemLeft.className = "flex items-center gap-2 truncate";

        const itemCheck = document.createElement("input");
        itemCheck.type = "checkbox";
        itemCheck.className = "rounded border-slate-600 text-indigo-500 focus:ring-0 cursor-pointer";
        itemCheck.checked = selectedLayerKeys.has(it.layer_name);

        const colorDot = document.createElement("span");
        colorDot.className = "w-2.5 h-2.5 rounded-full shrink-0 border border-black/30";
        colorDot.style.backgroundColor = it.style?.color || "#4B5563";

        const labelSpan = document.createElement("span");
        labelSpan.className = "truncate text-[11px] text-slate-300";
        labelSpan.innerHTML = `<span class="font-mono text-[10px] text-indigo-300 mr-1">${it.code}</span>${it.minor || it.layer_name}`;

        itemLeft.appendChild(itemCheck);
        itemLeft.appendChild(colorDot);
        itemLeft.appendChild(labelSpan);

        const itemRight = document.createElement("div");
        itemRight.className = "flex items-center gap-1.5 shrink-0";

        if (it.has_elevation) {
          const elevTag = document.createElement("span");
          elevTag.className = "px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 text-[9px] font-semibold";
          elevTag.textContent = "3D";
          elevTag.title = "Z 고도값 포함";
          itemRight.appendChild(elevTag);
        }

        const countBadge = document.createElement("span");
        countBadge.className = "text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 font-mono";
        countBadge.textContent = `${it.feature_count}`;
        itemRight.appendChild(countBadge);

        itemRow.appendChild(itemLeft);
        itemRow.appendChild(itemRight);
        itemsContainer.appendChild(itemRow);

        itemCheck.addEventListener("change", () => {
          if (itemCheck.checked) selectedLayerKeys.add(it.layer_name);
          else selectedLayerKeys.delete(it.layer_name);
          renderLayerTree(layerSearchInput.value);
          triggerPreviewUpdate();
        });
      });

      midBox.appendChild(itemsContainer);
      majBody.appendChild(midBox);
    });

    majCard.appendChild(majBody);
    layerTreeContainer.appendChild(majCard);
  });

  selectedSummaryBadge.textContent = `${selectedLayerKeys.size}개 선택됨`;
  btnExportMap.disabled = (selectedLayerKeys.size === 0);
}

function triggerPreviewUpdate() {
  clearTimeout(previewDebounceTimer);
  previewDebounceTimer = setTimeout(fetchAndRenderPreview, 300);
}

async function fetchAndRenderPreview() {
  if (!currentSessionId || selectedLayerKeys.size === 0) {
    vectorLayerGroup.clearLayers();
    labelLayerGroup.clearLayers();
    elevationStatsPill.classList.add("hidden");
    return;
  }

  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selected_layers: Array.from(selectedLayerKeys),
        clip_to_border: clipToBorderCheckbox ? clipToBorderCheckbox.checked : true
      })
    });

    if (!res.ok) throw new Error("미리보기 데이터를 불러오지 못했습니다.");
    const geojson = await res.json();
    window.lastPreviewGeojson = geojson;

    vectorLayerGroup.clearLayers();
    labelLayerGroup.clearLayers();

    let minElev = Infinity;
    let maxElev = -Infinity;
    let visibleCount = 0;

    const glayer = L.geoJSON(geojson, {
      style: (feat) => {
        const p = feat.properties || {};
        const isHighlight = (p.layer === "HIGHLIGHT");
        const isCadastral = (p.layer === "CADASTRAL");
        const isBorder = (p.layer === "BORDER");
        
        let color = p.color || "#64748B";
        let weight = 1.5;
        let fillOpacity = 0.15;
        let dashArray = undefined;

        if (isHighlight) {
          // Target Parcel Boundary (대지경계선) - Strong Red contrast
          color = "#EF4444";
          weight = 3.5;
          fillOpacity = 0.35;
        } else if (isCadastral) {
          // Adjacent Parcels - Soft Gray
          color = "#64748B";
          weight = 1.3;
          fillOpacity = 0.05;
        } else if (isBorder) {
          // Virtual frame - Muted Gray dashed
          color = "#64748B";
          weight = 1.5;
          fillOpacity = 0.0;
          dashArray = "6, 4";
        } else if (p.code?.startsWith("F001")) {
          // Contours: Major index 2.0px vs Minor 1.0px
          if (p.code === "F0017113") {
            color = "#94A3B8";
            weight = 2.0;
          } else {
            color = "#475569";
            weight = 0.9;
          }
        } else if (p.code?.startsWith("B001")) {
          // Existing buildings
          color = "#64748B";
          fillOpacity = 0.35;
          weight = 2.0;
        } else if (p.code?.startsWith("A002")) {
          // Road centerline
          color = "#64748B";
          weight = 1.2;
          dashArray = "6, 4";
        } else if (p.code?.startsWith("A001")) {
          // Road boundary
          color = "#64748B";
          weight = 1.8;
        } else if (p.code?.startsWith("C001") || p.code?.startsWith("E001")) {
          // Water
          color = "#64748B";
          fillOpacity = 0.25;
          weight = 1.5;
        }

        return {
          color: color,
          weight: weight,
          opacity: 0.95,
          fillColor: color,
          fillOpacity: fillOpacity,
          dashArray: dashArray
        };
      },
      pointToLayer: (feat, latlng) => {
        const p = feat.properties || {};
        if (p.layer === "LABEL" && p.text) {
          // Render textual label as a Leaflet DivIcon
          const divIcon = L.divIcon({
            className: 'jibeon-label-tag',
            html: `<div class="bg-slate-900/95 text-slate-200 border border-slate-700 px-1.5 py-0.2 rounded text-[11px] font-medium shadow-md whitespace-nowrap transform -translate-x-1/2 -translate-y-1/2 ${p.IS_TARGET === 'Y' ? 'text-red-400 border-red-500/80 font-bold' : ''}">${p.text}</div>`,
            iconSize: [0, 0]
          });
          return L.marker(latlng, { icon: divIcon });
        }

        return L.circleMarker(latlng, {
          radius: 3.5,
          fillColor: p.color || "#64748B",
          color: "#ffffff",
          weight: 1,
          opacity: 0.9,
          fillOpacity: 0.8
        });
      },
      onEachFeature: (feat, layer) => {
        visibleCount++;
        const p = feat.properties || {};
        if (p.elevation !== null && p.elevation !== undefined) {
          const e = parseFloat(p.elevation);
          if (!isNaN(e) && Math.abs(e) > 1e-4) {
            minElev = Math.min(minElev, e);
            maxElev = Math.max(maxElev, e);
          }
        }

        let popup = `<div class="text-xs space-y-1">
          <div class="font-bold text-slate-100 flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full" style="background:${p.color || '#3b82f6'}"></span>
            ${p.minor || p.layer}
          </div>
          <div class="text-[11px] text-slate-400">
            <span class="font-mono text-indigo-300">${p.code || '-'}</span> | ${p.major || '-'} &gt; ${p.mid || '-'}
          </div>`;
        if (p.JIBUN) {
          popup += `<div class="text-rose-300 font-semibold">지번: ${p.JIBUN} ${p.IS_TARGET === 'Y' ? '(★대상필지)' : ''}</div>`;
        }
        if (p.AREA_M2 !== undefined && p.AREA_M2 !== null && p.AREA_M2 > 0) {
          popup += `<div class="text-emerald-400 font-semibold">면적: ${p.AREA_M2.toLocaleString()} m² (${p.AREA_PYUNG}평)</div>`;
        }
        if (p.elevation !== null && p.elevation !== undefined && Math.abs(p.elevation) > 1e-4) {
          popup += `<div class="text-amber-400 font-semibold">표고(고도): ${p.elevation}m</div>`;
        }
        if (p.text) {
          popup += `<div class="text-slate-200">주기텍스트: ${p.text}</div>`;
        }
        popup += `</div>`;
        layer.bindPopup(popup);
      }
    });

    vectorLayerGroup.addLayer(glayer);

    statVisibleFeatures.textContent = `${visibleCount.toLocaleString()}개`;
    if (minElev !== Infinity) {
      statElevRange.textContent = `${minElev.toFixed(1)}m ~ ${maxElev.toFixed(1)}m`;
    } else {
      statElevRange.textContent = "지적도/평면(2D)";
    }
    elevationStatsPill.classList.remove("hidden");

  } catch (err) {
    console.error("Preview error:", err);
  }
}

// Safe Response Error Parser (Prevents JSON syntax error on 500 HTML/text responses)
async function parseResponseError(res, fallbackMessage) {
  try {
    const data = await res.json();
    if (data && data.detail) {
      return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    }
    return fallbackMessage;
  } catch (e) {
    try {
      const text = await res.text();
      return text || fallbackMessage;
    } catch (e2) {
      return fallbackMessage;
    }
  }
}

// Jibeon Fetch Handler
async function handleJibeonFetch() {
  const address = jibeonAddressInput.value.trim();
  if (!address) {
    alert("지번 또는 도로명 주소를 입력해주세요. (예: 고덕동 2728)");
    jibeonAddressInput.focus();
    return;
  }

  showLoading(`'${address}' 지적도 검색 및 주변 필지 수집 중 (VWorld)...`);
  jibeonStatusBadge.textContent = "검색 중...";
  jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400";

  try {
    const res = await fetch("/api/jibeon/fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address: address,
        buffer_meters: getBufferMeters(),
        border_shape: jibeonShapeSelect.value || "rectangle",
        session_id: currentSessionId
      })
    });

    if (!res.ok) {
      const errMsg = await parseResponseError(res, "지적도 검색 실패");
      throw new Error(errMsg);
    }

    const data = await res.json();
    currentSessionId = data.session_id;
    currentLayers = data.layer_summaries || [];

    // UI Updates
    if (jibeonAddressInput) jibeonAddressInput.value = data.address;
    if (mobileQuickAddress) {
      mobileQuickAddress.value = data.address;
      if (btnMobileClearAddr) btnMobileClearAddr.classList.remove("hidden");
    }
    jibeonStatusBadge.textContent = "연동 완료";
    jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    
    jibeonInfoCard.classList.remove("hidden");
    jibeonTargetName.textContent = `${data.address} (${data.target_label})`;
    jibeonPnuText.textContent = `PNU: ${data.target_pnu}`;
    if (jibeonAreaText) {
      if (data.target_area_m2 && data.target_area_m2 > 0) {
        jibeonAreaText.textContent = `${data.target_area_m2.toLocaleString()} ㎡ (${data.target_area_pyung.toLocaleString()}평)`;
      } else {
        jibeonAreaText.textContent = "-";
      }
    }

    // Check distance alert
    if (data.distance_info && data.distance_info.is_far) {
      if (distanceAlertBox) {
        distanceAlertBox.classList.remove("hidden");
        distanceAlertDesc.innerHTML = `검색하신 지번(<strong>${data.address}</strong>)과 업로드된 수치지형도의 도면 위치 간 거리가 <strong>약 ${data.distance_info.distance_km}km</strong> 떨어져 있습니다.<br/>이 상태로 CAD 내보내기 시 서로 다른 위치에 그려져 따로 놀게 됩니다.`;
      }
    } else {
      if (distanceAlertBox) distanceAlertBox.classList.add("hidden");
    }

    // Automatically select cadastral layers
    data.cadastral_layer_keys.forEach(k => selectedLayerKeys.add(k));

    renderLayerTree();

    if (data.bounds_wgs84 && data.bounds_wgs84.length === 2) {
      map.fitBounds(data.bounds_wgs84, { padding: [50, 50] });
    }

    triggerPreviewUpdate();
    if (window.innerWidth < 768) setMobileDrawer(false);

  } catch (err) {
    alert("지적도 검색 오류: " + err.message);
    jibeonStatusBadge.textContent = "오류";
    jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-red-500/20 text-red-400";
  } finally {
    hideLoading();
  }
}

// Map Center Cadastral Sync Handler (One-click)
async function handleSyncTopoCadastral() {
  if (!currentSessionId) {
    alert("수치지형도를 먼저 업로드해주세요.");
    return;
  }

  showLoading("업로드된 수치지형도 위치의 지적도(지번) 자동 호출 중 (VWorld)...");
  jibeonStatusBadge.textContent = "연동 중...";
  jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400";

  try {
    const res = await fetch("/api/jibeon/fetch-by-map-center", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        buffer_meters: getBufferMeters(),
        border_shape: jibeonShapeSelect.value || "rectangle"
      })
    });

    if (!res.ok) {
      const errMsg = await parseResponseError(res, "지적도 연동 실패");
      throw new Error(errMsg);
    }

    const data = await res.json();
    currentLayers = data.layer_summaries || [];
    
    // Select cadastral layers
    data.cadastral_layer_keys.forEach(k => selectedLayerKeys.add(k));

    // Update UI
    if (jibeonAddressInput) jibeonAddressInput.value = data.address;
    if (mobileQuickAddress) {
      mobileQuickAddress.value = data.address;
      if (btnMobileClearAddr) btnMobileClearAddr.classList.remove("hidden");
    }
    jibeonStatusBadge.textContent = "도면 위치 연동됨";
    jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    jibeonInfoCard.classList.remove("hidden");
    jibeonTargetName.textContent = data.address;
    jibeonPnuText.textContent = `PNU: ${data.target_pnu || "도면 중심 필지"}`;
    if (jibeonAreaText) {
      if (data.target_area_m2 && data.target_area_m2 > 0) {
        jibeonAreaText.textContent = `${data.target_area_m2.toLocaleString()} ㎡ (${data.target_area_pyung.toLocaleString()}평)`;
      } else {
        jibeonAreaText.textContent = "-";
      }
    }
    jibeonAddressInput.value = data.address;
    if (distanceAlertBox) distanceAlertBox.classList.add("hidden");

    renderLayerTree();
    triggerPreviewUpdate();
    if (window.innerWidth < 768) setMobileDrawer(false);

  } catch (err) {
    alert("지적도 자동 결합 오류: " + err.message);
    jibeonStatusBadge.textContent = "오류";
    jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-red-500/20 text-red-400";
  } finally {
    hideLoading();
  }
}

// Parcel-centered 3D Topographic Contour Generator Handler (One-click)
async function handleGenerateTopoForParcel() {
  const addr = (jibeonAddressInput && jibeonAddressInput.value.trim()) || 
               (mobileQuickAddress && mobileQuickAddress.value.trim());

  if (!currentSessionId) {
    if (addr) {
      // First fetch cadastral parcel for the address
      await handleJibeonFetch();
      if (!currentSessionId) return;
    } else {
      alert("💡 먼저 검색창에 지번 또는 주소를 검색해 주세요.\n(예: 고덕동 2728, 역삼동 737, 서초동 1303-37)");
      if (window.innerWidth < 768 && mobileQuickAddress) {
        mobileQuickAddress.focus();
      } else if (jibeonAddressInput) {
        setMobileDrawer(true);
        jibeonAddressInput.focus();
      }
      return;
    }
  }

  const currentAddr = (jibeonAddressInput && jibeonAddressInput.value.trim()) || "현재 위치";
  showLoading(`'${currentAddr}' 위치의 3D 등고선(수치지형도) 생성 및 결합 중...`);

  try {
    const res = await fetch("/api/topo/generate-for-current-parcel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        buffer_meters: getBufferMeters(),
        border_shape: jibeonShapeSelect ? (jibeonShapeSelect.value || "rectangle") : "rectangle"
      })
    });

    if (!res.ok) {
      const errMsg = await parseResponseError(res, "3D 수치지형도 생성 실패");
      throw new Error(errMsg);
    }

    const data = await res.json();
    currentLayers = data.layer_summaries || [];

    // Automatically select the new 3D topo layers (주곡선, 계곡선, 표고점)
    if (data.topo_layer_keys) {
      data.topo_layer_keys.forEach(k => selectedLayerKeys.add(k));
    }

    renderLayerTree();
    triggerPreviewUpdate();

    if (window.innerWidth < 768) {
      setMobileDrawer(false);
    }

    // Success notification toast
    const toast = document.createElement("div");
    toast.className = "fixed top-20 left-1/2 -translate-x-1/2 bg-indigo-600/95 text-white text-xs font-bold px-4 py-2 rounded-full shadow-2xl z-[99999] border border-indigo-400 flex items-center gap-2";
    toast.innerHTML = `<i class="ph-bold ph-check-circle text-base text-emerald-300"></i><span>${data.message || "3D 수치지형도 결합 완료"}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = "opacity 0.4s ease";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 400);
    }, 3200);

  } catch (err) {
    alert("3D 수치지형도 결합 오류: " + err.message);
  } finally {
    hideLoading();
  }
}

// Upload file handler (Topographic map, single or multi-sheet)
async function handleFileUpload(fileOrFiles) {
  let fileList = [];
  if (fileOrFiles instanceof FileList) {
    fileList = Array.from(fileOrFiles);
  } else if (Array.isArray(fileOrFiles)) {
    fileList = fileOrFiles;
  } else if (fileOrFiles) {
    fileList = [fileOrFiles];
  }
  if (fileList.length === 0) return;

  const summaryName = fileList.length === 1 ? fileList[0].name : `${fileList[0].name} 외 ${fileList.length - 1}개 도엽`;
  showLoading(`수치지형도 분석 및 통합 중 (${summaryName})...`);

  const formData = new FormData();
  fileList.forEach(f => {
    formData.append("files", f);
  });
  // Fallback single file field
  formData.append("file", fileList[0]);
  if (currentSessionId) {
    formData.append("session_id", currentSessionId);
  }

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errMsg = await parseResponseError(res, "업로드에 실패했습니다.");
      throw new Error(errMsg);
    }

    const data = await res.json();
    currentSessionId = data.session_id;
    currentLayers = data.layer_summaries || [];

    fileInfoCard.classList.remove("hidden");
    fileNameEl.textContent = data.file_name;
    fileCrsBadge.textContent = data.crs;
    exportCrsSelect.value = "SAME";

    if (data.detected_address && topoDetectedAddr) {
      topoDetectedAddr.textContent = data.detected_address;
    }

    const totalFeats = currentLayers.reduce((acc, x) => acc + x.feature_count, 0);
    layerCountInfo.textContent = `총 ${currentLayers.length}개 레이어`;
    featCountInfo.textContent = `${totalFeats.toLocaleString()}개 객체`;
    uploadStatusBadge.textContent = "분석 완료";
    uploadStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";

    // Preserve existing cadastral selections if any, and select all layers
    const prevCadastral = ["HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"].filter(k => selectedLayerKeys.has(k) || (data.cadastral_layer_keys && data.cadastral_layer_keys.includes(k)));
    selectedLayerKeys = new Set(currentLayers.map(l => l.layer_name));
    prevCadastral.forEach(k => selectedLayerKeys.add(k));

    renderLayerTree();

    if (data.bounds_wgs84 && data.bounds_wgs84.length === 2) {
      map.fitBounds(data.bounds_wgs84, { padding: [40, 40] });
    }

    triggerPreviewUpdate();

  } catch (err) {
    alert("오류: " + err.message);
    uploadStatusBadge.textContent = "오류 발생";
    uploadStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30";
  } finally {
    hideLoading();
  }
}

async function loadSampleData() {
  showLoading("표준 견본 수치지형도 생성 및 로드 중...");
  try {
    const res = await fetch("/api/sample");
    if (!res.ok) throw new Error("샘플 데이터를 가져오지 못했습니다.");
    const blob = await res.blob();
    const sampleFile = new File([blob], "37608044_2020_SAMPLE.dxf", { type: "application/dxf" });
    await handleFileUpload(sampleFile);
  } catch (e) {
    alert("샘플 로드 실패: " + e.message);
  } finally {
    hideLoading();
  }
}

function applyPreset(presetKey) {
  const p = presets[presetKey];
  if (!p) return;

  const savedCadastral = Array.from(selectedLayerKeys).filter(k => ["HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"].includes(k));
  selectedLayerKeys.clear();
  savedCadastral.forEach(k => selectedLayerKeys.add(k));

  const rule = p.rule || {};

  currentLayers.forEach(l => {
    let match = false;
    if (["HIGHLIGHT", "CADASTRAL", "LABEL", "BORDER"].includes(l.layer_name)) match = true;
    if (rule.majors && rule.majors.includes(l.major)) match = true;
    if (rule.mids && rule.mids.includes(l.mid)) match = true;
    if (rule.codes && rule.codes.some(c => l.code.startsWith(c) || c.startsWith(l.code))) match = true;

    if (match) selectedLayerKeys.add(l.layer_name);
  });

  renderLayerTree(layerSearchInput.value);
  triggerPreviewUpdate();
}

// --- Custom Layer Presets (localStorage) ---
const CUSTOM_PRESETS_KEY = "ngii_custom_layer_presets_v1";

function loadCustomPresets() {
  try {
    const raw = localStorage.getItem(CUSTOM_PRESETS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveCustomPresetsToStorage(presetsList) {
  try {
    localStorage.setItem(CUSTOM_PRESETS_KEY, JSON.stringify(presetsList));
  } catch (e) {
    console.error("Failed to save custom presets", e);
  }
}

function renderCustomPresets() {
  if (!customPresetsContainer) return;
  customPresetsContainer.innerHTML = "";
  const list = loadCustomPresets();
  if (list.length === 0) {
    customPresetsContainer.classList.add("hidden");
    return;
  }
  customPresetsContainer.classList.remove("hidden");

  list.forEach(item => {
    const chip = document.createElement("div");
    chip.className = "group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-750 hover:bg-slate-700 text-slate-200 text-xs border border-slate-650 transition cursor-pointer shadow-sm";
    
    const nameSpan = document.createElement("span");
    nameSpan.className = "truncate max-w-[120px] font-medium";
    nameSpan.textContent = item.name;
    nameSpan.title = `${item.name} (${item.layers.length}개 레이어)`;
    nameSpan.addEventListener("click", () => {
      applyCustomPreset(item);
    });

    const cntSpan = document.createElement("span");
    cntSpan.className = "text-[10px] px-1 py-0.2 rounded bg-slate-900 text-indigo-300 font-mono";
    cntSpan.textContent = `${item.layers.length}`;

    const delBtn = document.createElement("button");
    delBtn.className = "text-slate-400 hover:text-red-400 text-xs ml-0.5 transition";
    delBtn.innerHTML = "&times;";
    delBtn.title = "프리셋 삭제";
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteCustomPreset(item.id);
    });

    chip.appendChild(nameSpan);
    chip.appendChild(cntSpan);
    chip.appendChild(delBtn);
    customPresetsContainer.appendChild(chip);
  });
}

function applyCustomPreset(preset) {
  if (!preset || !preset.layers) return;
  selectedLayerKeys.clear();
  preset.layers.forEach(k => selectedLayerKeys.add(k));
  renderLayerTree(layerSearchInput.value);
  triggerPreviewUpdate();
}

function handleSaveCustomPreset() {
  if (selectedLayerKeys.size === 0) {
    alert("먼저 저장할 레이어를 1개 이상 선택해주세요.");
    return;
  }
  const defaultName = `맞춤 세트 ${new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}`;
  const name = prompt("저장할 프리셋 이름을 입력하세요:", defaultName);
  if (!name || !name.trim()) return;

  const list = loadCustomPresets();
  list.push({
    id: Date.now(),
    name: name.trim(),
    layers: Array.from(selectedLayerKeys)
  });
  saveCustomPresetsToStorage(list);
  renderCustomPresets();
}

function deleteCustomPreset(id) {
  let list = loadCustomPresets();
  list = list.filter(it => it.id !== id);
  saveCustomPresetsToStorage(list);
  renderCustomPresets();
}

function extractFilename(res, defaultExt) {
  // Strategy 1: Check explicit X-Suggested-Filename header
  const customHeader = res.headers.get("x-suggested-filename");
  if (customHeader) {
    try {
      const decoded = decodeURIComponent(customHeader);
      if (decoded && decoded.trim()) return decoded.trim();
    } catch (e) {}
  }

  // Strategy 2: Check Content-Disposition header (RFC 5987 filename*= and filename="...")
  const disposition = res.headers.get("content-disposition");
  if (disposition) {
    // Check RFC 5987 format: filename*=UTF-8''...
    const utf8Match = disposition.match(/filename\*=(?:UTF-8'')?([^;]+)/i);
    if (utf8Match && utf8Match[1]) {
      try {
        let clean = utf8Match[1].replace(/['"]/g, "").trim();
        const decoded = decodeURIComponent(clean);
        if (decoded) return decoded;
      } catch (e) {}
    }

    // Check standard format: filename="..."
    const standardMatch = disposition.match(/filename="?([^";]+)"?/i);
    if (standardMatch && standardMatch[1]) {
      try {
        let clean = standardMatch[1].trim();
        return clean.includes("%") ? decodeURIComponent(clean) : clean;
      } catch (e) {
        return standardMatch[1].trim();
      }
    }
  }

  // Strategy 3: Guaranteed client-side smart filename reconstruction
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const todayStr = `${year}${month}${day}`;

  const addrInput = jibeonAddressInput ? jibeonAddressInput.value.trim() : "";
  const topoText = fileNameEl && fileNameEl.textContent ? fileNameEl.textContent.trim() : "";

  const cleanAddr = addrInput ? addrInput.replace(/[^\w가-힣]/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "") : "";
  const cleanTopo = (topoText && topoText !== "도엽명") ? topoText.replace(/\.[^/.]+$/, "").replace(/[^\w가-힣]/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "") : "";

  if (cleanAddr && cleanTopo) {
    return `[${cleanAddr}]_(${cleanTopo})_현황도_${todayStr}.${defaultExt}`;
  } else if (cleanAddr) {
    return `[${cleanAddr}]_현황도_${todayStr}.${defaultExt}`;
  } else if (cleanTopo) {
    return `${cleanTopo}_현황도_${todayStr}.${defaultExt}`;
  }

  return `통합_현황도_${todayStr}.${defaultExt}`;
}

async function exportCustomMap() {
  if (!currentSessionId || selectedLayerKeys.size === 0) {
    alert("선택된 레이어가 없습니다.");
    return;
  }

  showLoading(`선택한 레이어로 ${currentExportFormat.toUpperCase()} 통합 도면 파일 생성 중...`);

  try {
    const res = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selected_layers: Array.from(selectedLayerKeys),
        format: currentExportFormat,
        target_crs: exportCrsSelect.value,
        clip_to_border: clipToBorderCheckbox ? clipToBorderCheckbox.checked : true,
        unify_bylayer: dxfBylayerCheckbox ? dxfBylayerCheckbox.checked : true,
        include_drawing_elements: dxfElementsCheckbox ? dxfElementsCheckbox.checked : true
      })
    });

    if (!res.ok) {
      const errMsg = await parseResponseError(res, "내보내기 실패");
      throw new Error(errMsg);
    }

    const blob = await res.blob();
    const defaultExt = currentExportFormat === "shp" ? "zip" : (currentExportFormat === "html" ? "html" : currentExportFormat);
    const filename = extractFilename(res, defaultExt);

    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);

  } catch (err) {
    alert("내보내기 오류: " + err.message);
  } finally {
    hideLoading();
  }
}

// --- Mobile Drawer & Navigation Management ---
function setMobileDrawer(isOpen) {
  if (!sidebarPanel) return;
  if (isOpen) {
    sidebarPanel.classList.remove("drawer-closed");
    sidebarPanel.classList.add("drawer-open");
    if (toggleDrawerIcon) toggleDrawerIcon.className = "ph-bold ph-x";
    if (toggleDrawerLabel) toggleDrawerLabel.textContent = "지도";
  } else {
    sidebarPanel.classList.remove("drawer-open");
    sidebarPanel.classList.add("drawer-closed");
    if (toggleDrawerIcon) toggleDrawerIcon.className = "ph-bold ph-sliders";
    if (toggleDrawerLabel) toggleDrawerLabel.textContent = "제어판";
    document.querySelectorAll(".mobile-nav-btn").forEach(b => {
      if (b.getAttribute("data-tab") === "map") {
        b.classList.add("active", "text-indigo-400");
        b.classList.remove("text-slate-400");
      } else {
        b.classList.remove("active", "text-indigo-400");
        if (b.getAttribute("data-tab") !== "export" && b.getAttribute("data-tab") !== "gps") {
          b.classList.add("text-slate-400");
        }
      }
    });
    setTimeout(() => { if (map) map.invalidateSize(); }, 320);
  }
}

function scrollToSection(sectionId) {
  setMobileDrawer(true);
  setTimeout(() => {
    const el = document.getElementById(sectionId);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 120);
}

// GPS Fetch Handler (Smartphone field location)
async function handleGpsFetch() {
  if (!navigator.geolocation) {
    alert("이 기기 또는 브라우저에서 GPS 위치 서비스를 지원하지 않습니다.");
    return;
  }

  showLoading("스마트폰 현장 GPS 위치 수신 중...");

  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      showLoading(`현장 좌표 수신 완료 (${lat.toFixed(5)}, ${lng.toFixed(5)}). 지적도 호출 중...`);

      try {
        const res = await fetch("/api/jibeon/fetch-by-gps", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            latitude: lat,
            longitude: lng,
            buffer_meters: getBufferMeters(),
            border_shape: jibeonShapeSelect ? (jibeonShapeSelect.value || "rectangle") : "rectangle",
            session_id: currentSessionId
          })
        });

        if (!res.ok) {
          const errMsg = await parseResponseError(res, "GPS 위치 지적도 호출 실패");
          throw new Error(errMsg);
        }

        const data = await res.json();
        currentSessionId = data.session_id;
        currentLayers = data.layer_summaries || [];

        // UI Updates
        if (jibeonAddressInput) jibeonAddressInput.value = data.address;
        if (jibeonStatusBadge) {
          jibeonStatusBadge.textContent = "현장 GPS 연동됨";
          jibeonStatusBadge.className = "text-[11px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        }
        if (jibeonInfoCard) jibeonInfoCard.classList.remove("hidden");
        if (jibeonTargetName) jibeonTargetName.textContent = `${data.address} (${data.target_label})`;
        if (jibeonPnuText) jibeonPnuText.textContent = `PNU: ${data.target_pnu}`;
        if (jibeonAreaText) {
          if (data.target_area_m2 && data.target_area_m2 > 0) {
            jibeonAreaText.textContent = `${data.target_area_m2.toLocaleString()} ㎡ (${data.target_area_pyung.toLocaleString()}평)`;
          } else {
            jibeonAreaText.textContent = "-";
          }
        }

        data.cadastral_layer_keys.forEach(k => selectedLayerKeys.add(k));
        renderLayerTree();

        if (data.bounds_wgs84 && data.bounds_wgs84.length === 2) {
          map.fitBounds(data.bounds_wgs84, { padding: [40, 40] });
        }

        triggerPreviewUpdate();

        // On mobile, close drawer to view map right away
        setMobileDrawer(false);

      } catch (err) {
        alert("GPS 지적도 호출 오류: " + err.message);
      } finally {
        hideLoading();
      }
    },
    (err) => {
      hideLoading();
      let msg = "위치 수신에 실패했습니다.";
      if (err.code === 1) msg = "위치 정보 접근 권한이 차단되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.";
      else if (err.code === 2) msg = "GPS 신호를 수신할 수 없습니다.";
      else if (err.code === 3) msg = "위치 수신 시간이 초과되었습니다.";
      alert(msg);
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

function setupEvents() {
  // Jibeon Search
  btnFetchJibeon.addEventListener("click", handleJibeonFetch);
  jibeonAddressInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleJibeonFetch();
  });

  if (btnSyncTopoCadastral) {
    btnSyncTopoCadastral.addEventListener("click", handleSyncTopoCadastral);
  }
  if (btnFixToTopoCenter) {
    btnFixToTopoCenter.addEventListener("click", handleSyncTopoCadastral);
  }

  if (clipToBorderCheckbox) {
    clipToBorderCheckbox.addEventListener("change", () => {
      triggerPreviewUpdate();
    });
  }

  jibeonShapeSelect.addEventListener("change", () => {
    if (jibeonAddressInput.value.trim()) {
      handleJibeonFetch();
    } else if (currentSessionId) {
      handleSyncTopoCadastral();
    }
  });

  jibeonBufferSelect.addEventListener("change", () => {
    if (jibeonBufferSelect.value === "custom") {
      if (jibeonBufferCustom) {
        jibeonBufferCustom.classList.remove("hidden");
        jibeonBufferCustom.focus();
      }
      return;
    } else {
      if (jibeonBufferCustom) jibeonBufferCustom.classList.add("hidden");
    }
    if (jibeonAddressInput.value.trim()) {
      handleJibeonFetch();
    } else if (currentSessionId) {
      handleSyncTopoCadastral();
    }
  });

  if (jibeonBufferCustom) {
    jibeonBufferCustom.addEventListener("change", () => {
      if (jibeonAddressInput.value.trim()) {
        handleJibeonFetch();
      } else if (currentSessionId) {
        handleSyncTopoCadastral();
      }
    });
    jibeonBufferCustom.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        if (jibeonAddressInput.value.trim()) {
          handleJibeonFetch();
        } else if (currentSessionId) {
          handleSyncTopoCadastral();
        }
      }
    });
  }

  // Topo Upload Dropzone
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("border-indigo-400", "bg-slate-700/50");
  });
  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("border-indigo-400", "bg-slate-700/50");
  });
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("border-indigo-400", "bg-slate-700/50");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files);
    }
  });

  if (btnSaveCustomPreset) {
    btnSaveCustomPreset.addEventListener("click", handleSaveCustomPreset);
  }

  // Presets
  document.querySelectorAll(".preset-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const presetId = btn.getAttribute("data-preset");
      applyPreset(presetId);
    });
  });

  btnSelectAll.addEventListener("click", () => {
    currentLayers.forEach(l => selectedLayerKeys.add(l.layer_name));
    renderLayerTree(layerSearchInput.value);
    triggerPreviewUpdate();
  });

  btnDeselectAll.addEventListener("click", () => {
    selectedLayerKeys.clear();
    renderLayerTree(layerSearchInput.value);
    triggerPreviewUpdate();
  });

  layerSearchInput.addEventListener("input", (e) => {
    renderLayerTree(e.target.value);
  });

  document.querySelectorAll(".fmt-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".fmt-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentExportFormat = btn.getAttribute("data-format");
    });
  });

  btnExportMap.addEventListener("click", exportCustomMap);

  if (btnLoadSample) {
    btnLoadSample.addEventListener("click", async (e) => {
      e.stopPropagation();
      await loadSampleData();
      if (window.innerWidth < 768) setMobileDrawer(false);
    });
  }

  // 3D Topographic Contour Combine Buttons
  if (btnHeaderCombineTopo) {
    btnHeaderCombineTopo.addEventListener("click", handleGenerateTopoForParcel);
  }
  if (btnCardCombineTopo) {
    btnCardCombineTopo.addEventListener("click", handleGenerateTopoForParcel);
  }

  // --- Mobile Specific Event Listeners ---
  if (btnMobileToggleDrawer) {
    btnMobileToggleDrawer.addEventListener("click", () => {
      const isClosed = sidebarPanel && sidebarPanel.classList.contains("drawer-closed");
      setMobileDrawer(isClosed);
    });
  }

  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener("click", () => setMobileDrawer(false));
  }

  // --- Mobile Floating Address Search Bar ---
  if (mobileQuickAddress) {
    mobileQuickAddress.addEventListener("input", (e) => {
      if (jibeonAddressInput) jibeonAddressInput.value = e.target.value;
      if (btnMobileClearAddr) {
        if (e.target.value.trim().length > 0) btnMobileClearAddr.classList.remove("hidden");
        else btnMobileClearAddr.classList.add("hidden");
      }
    });
    mobileQuickAddress.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleJibeonFetch();
      }
    });
  }

  if (jibeonAddressInput && mobileQuickAddress) {
    jibeonAddressInput.addEventListener("input", (e) => {
      mobileQuickAddress.value = e.target.value;
      if (btnMobileClearAddr) {
        if (e.target.value.trim().length > 0) btnMobileClearAddr.classList.remove("hidden");
        else btnMobileClearAddr.classList.add("hidden");
      }
    });
  }

  if (btnMobileQuickSearch) {
    btnMobileQuickSearch.addEventListener("click", () => {
      handleJibeonFetch();
    });
  }

  if (btnMobileClearAddr) {
    btnMobileClearAddr.addEventListener("click", () => {
      if (mobileQuickAddress) mobileQuickAddress.value = "";
      if (jibeonAddressInput) jibeonAddressInput.value = "";
      btnMobileClearAddr.classList.add("hidden");
      if (mobileQuickAddress) mobileQuickAddress.focus();
    });
  }

  // Mobile Bottom Navigation Bar Tabs
  document.querySelectorAll(".mobile-nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      document.querySelectorAll(".mobile-nav-btn").forEach(b => {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      
      if (tab === "jibeon") {
        setMobileDrawer(false);
        if (mobileQuickAddress) {
          mobileQuickAddress.focus();
          mobileQuickAddress.select();
        }
      } else if (tab === "topo") {
        // Direct 1-click 3D topo generation for searched address
        handleGenerateTopoForParcel();
      } else if (tab === "map") {
        setMobileDrawer(false);
        if (map && vectorLayerGroup && vectorLayerGroup.getLayers().length > 0) {
          try {
            const b = vectorLayerGroup.getBounds();
            if (b.isValid()) map.fitBounds(b, { padding: [40, 40] });
          } catch(e){}
        }
      } else if (tab === "export") {
        scrollToSection("section-export");
      }
    });
  });
}

async function fetchPresets() {
  try {
    const res = await fetch("/api/presets");
    if (res.ok) presets = await res.json();
  } catch (e) {
    console.error("Failed to load presets", e);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initMap();
  setupEvents();
  fetchPresets();
  renderCustomPresets();
});


// ===== 지적 생성구역 + 위성영상 PNG 이미지 저장 =====
(function () {
  const btn = document.getElementById("btn-export-sat-image");
  if (!btn) return;

  const TILE = 256;
  const lonToX = (lon, z) => ((lon + 180) / 360) * TILE * Math.pow(2, z);
  const latToY = (lat, z) => {
    const r = lat * Math.PI / 180;
    return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * TILE * Math.pow(2, z);
  };

  function eachCoord(geom, fn) {
    if (!geom) return;
    const walk = (c) => {
      if (typeof c[0] === "number") fn(c[0], c[1]);
      else c.forEach(walk);
    };
    walk(geom.coordinates || []);
  }

  function loadTile(z, x, y) {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = `/api/tile/sat/${z}/${x}/${y}`;
    });
  }

  async function exportSatImage() {
    const gj = window.lastPreviewGeojson;
    const feats = ((gj && gj.features) || []).filter(f =>
      f.properties && ["CADASTRAL", "HIGHLIGHT", "LABEL"].includes(f.properties.layer));
    const parcels = feats.filter(f => f.properties.layer !== "LABEL");
    if (parcels.length === 0) {
      alert("먼저 지번을 검색해서 지적도를 생성해 주세요.");
      return;
    }

    // 지적 구역 경계 계산
    let minLon = 999, maxLon = -999, minLat = 999, maxLat = -999;
    parcels.forEach(f => eachCoord(f.geometry, (lon, lat) => {
      minLon = Math.min(minLon, lon); maxLon = Math.max(maxLon, lon);
      minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
    }));

    // 가로 2400px 이하에서 가장 높은 줌 선택
    let z = 19;
    while (z > 12 && (lonToX(maxLon, z) - lonToX(minLon, z)) > 2400) z--;

    const x0 = lonToX(minLon, z), x1 = lonToX(maxLon, z);
    const y0 = latToY(maxLat, z), y1 = latToY(minLat, z);
    const W = Math.ceil(x1 - x0), H = Math.ceil(y1 - y0);

    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#222"; ctx.fillRect(0, 0, W, H);

    if (loadingOverlay) { loadingText.textContent = "위성영상 불러오는 중..."; loadingOverlay.classList.remove("hidden"); }
    try {
      // 위성 타일 합성
      const tx0 = Math.floor(x0 / TILE), tx1 = Math.floor(x1 / TILE);
      const ty0 = Math.floor(y0 / TILE), ty1 = Math.floor(y1 / TILE);
      const jobs = [];
      for (let tx = tx0; tx <= tx1; tx++) {
        for (let ty = ty0; ty <= ty1; ty++) {
          jobs.push(loadTile(z, tx, ty).then(img => {
            if (img) ctx.drawImage(img, tx * TILE - x0, ty * TILE - y0, TILE, TILE);
          }));
        }
      }
      await Promise.all(jobs);

      const px = (lon) => lonToX(lon, z) - x0;
      const py = (lat) => latToY(lat, z) - y0;

      // 필지 경계선
      const drawRing = (ring) => {
        ring.forEach((c, i) => i ? ctx.lineTo(px(c[0]), py(c[1])) : ctx.moveTo(px(c[0]), py(c[1])));
      };
      const order = parcels.sort((a, b) =>
        (a.properties.layer === "HIGHLIGHT") - (b.properties.layer === "HIGHLIGHT"));
      order.forEach(f => {
        const hl = f.properties.layer === "HIGHLIGHT";
        const g = f.geometry;
        if (!g) return;
        const polys = g.type === "Polygon" ? [g.coordinates]
          : g.type === "MultiPolygon" ? g.coordinates : [];
        ctx.lineJoin = "round";
        ctx.lineWidth = hl ? 3.5 : 1.3;
        ctx.strokeStyle = hl ? "#EF4444" : "rgba(226,232,240,0.9)";
        ctx.fillStyle = hl ? "rgba(239,68,68,0.35)" : "rgba(0,0,0,0)";
        polys.forEach(poly => {
          ctx.beginPath();
          poly.forEach(drawRing);
          ctx.fill(); ctx.stroke();
        });
        if (g.type === "LineString" || g.type === "MultiLineString") {
          const lines = g.type === "LineString" ? [g.coordinates] : g.coordinates;
          lines.forEach(l => { ctx.beginPath(); drawRing(l); ctx.stroke(); });
        }
      });

      // 지번 라벨
      const fs = Math.max(12, Math.min(22, Math.round(W / 90)));
      ctx.font = `600 ${fs}px "Malgun Gothic", "Apple SD Gothic Neo", sans-serif`;
      ctx.textBaseline = "middle"; ctx.textAlign = "center";
      feats.filter(f => f.properties.layer === "LABEL" && f.properties.text).forEach(f => {
        const [lon, lat] = f.geometry.coordinates;
        const x = px(lon), y = py(lat);
        if (x < 0 || y < 0 || x > W || y > H) return;
        const t = String(f.properties.text);
        const target = f.properties.IS_TARGET === "Y";
        const w = ctx.measureText(t).width + 12, h = fs + 8;
        ctx.fillStyle = "rgba(15,23,42,0.88)";
        ctx.fillRect(x - w / 2, y - h / 2, w, h);
        if (target) { ctx.strokeStyle = "#EF4444"; ctx.lineWidth = 1.5; ctx.strokeRect(x - w / 2, y - h / 2, w, h); }
        ctx.fillStyle = target ? "#F87171" : "#E2E8F0";
        ctx.fillText(t, x, y);
      });

      // 출처 표기
      ctx.font = `${Math.max(10, fs - 3)}px sans-serif`;
      ctx.textAlign = "right"; ctx.textBaseline = "bottom";
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.fillText("위성영상: VWorld / 지적: VWorld 연속지적도", W - 6, H - 4);

      canvas.toBlob((blob) => {
        if (!blob) { alert("이미지 생성에 실패했습니다."); return; }
        const addr = (typeof jibeonAddressInput !== "undefined" && jibeonAddressInput.value.trim()) || "지적";
        const name = `지적위성_${addr.replace(/[\\/:*?"<>|\s]+/g, "_")}_${new Date().toISOString().slice(0, 10)}.png`;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      }, "image/png");
    } finally {
      if (loadingOverlay) loadingOverlay.classList.add("hidden");
    }
  }

  btn.addEventListener("click", () => exportSatImage().catch(e => alert("이미지 저장 오류: " + e.message)));
})();
