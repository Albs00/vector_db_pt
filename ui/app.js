/**
 * PUGLIA TERMICA 2026 - AI CATALOG EXPLORER CLIENT APPLICATION
 * Handles: Live Search, Multi-Filter, On-Demand PDF Single-Page Viewer, Interactive Zoom & Pan
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const searchInput = document.getElementById("search-input");
  const searchBtn = document.getElementById("search-btn");
  const clearBtn = document.getElementById("clear-btn");
  const brandFilter = document.getElementById("brand-filter");
  const categoryFilter = document.getElementById("category-filter");
  const limitSelect = document.getElementById("limit-select");
  const catalogOnlyToggle = document.getElementById("catalog-only-toggle");

  const diagnosticBar = document.getElementById("diagnostic-bar");
  const matchBadge = document.getElementById("match-badge");
  const detectedBrandBadge = document.getElementById("detected-brand-badge");
  const queryEcho = document.getElementById("query-echo");
  const latencyVal = document.getElementById("latency-val");
  const countVal = document.getElementById("count-val");

  const resultsGrid = document.getElementById("results-grid");
  const emptyState = document.getElementById("empty-state");
  const loadingState = document.getElementById("loading-state");

  // Modal Elements
  const pdfModal = document.getElementById("pdf-modal");
  const modalPageNum = document.getElementById("modal-page-num");
  const sidebarPageNum = document.getElementById("sidebar-page-num");
  const pageIndicator = document.getElementById("page-indicator");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const pdfPageImg = document.getElementById("pdf-page-img");
  const imageSpinner = document.getElementById("image-spinner");
  const imageViewport = document.getElementById("image-viewport");
  const sidebarProductsList = document.getElementById("sidebar-products-list");
  const sidebarCount = document.getElementById("sidebar-count");

  const zoomInBtn = document.getElementById("zoom-in-btn");
  const zoomOutBtn = document.getElementById("zoom-out-btn");
  const zoomFitBtn = document.getElementById("zoom-fit-btn");
  const zoomLevel = document.getElementById("zoom-level");
  const prevPageBtn = document.getElementById("prev-page-btn");
  const nextPageBtn = document.getElementById("next-page-btn");

  // Tech / Compatibility Modal Elements
  const techModal = document.getElementById("tech-modal");
  const techModalBrand = document.getElementById("tech-modal-brand");
  const techModalFamily = document.getElementById("tech-modal-family");
  const techModalBtu = document.getElementById("tech-modal-btu");
  const techModalPtPill = document.getElementById("tech-modal-pt-pill");
  const techModalPtVal = document.getElementById("tech-modal-pt-val");
  const techModalMfgPill = document.getElementById("tech-modal-mfg-pill");
  const techModalMfgVal = document.getElementById("tech-modal-mfg-val");
  const techModalTitle = document.getElementById("tech-modal-title");
  const techModalGross = document.getElementById("tech-modal-gross");
  const techModalNet = document.getElementById("tech-modal-net");
  const techModalViewPdfBtn = document.getElementById("tech-modal-view-pdf-btn");
  const techModalCloseBtn = document.getElementById("tech-modal-close-btn");

  const techTabBtnKits = document.getElementById("tech-tab-btn-kits");
  const techTabCountKits = document.getElementById("tech-tab-count-kits");
  const techTabBtnAcc = document.getElementById("tech-tab-btn-accessories");
  const techTabCountAcc = document.getElementById("tech-tab-count-acc");
  const techTabBtnUnits = document.getElementById("tech-tab-btn-units");
  const techTabLabelUnits = document.getElementById("tech-tab-label-units");
  const techTabCountUnits = document.getElementById("tech-tab-count-units");
  const techTabBtnVariants = document.getElementById("tech-tab-btn-variants");
  const techTabCountVariants = document.getElementById("tech-tab-count-variants");

  const techPaneKits = document.getElementById("tech-pane-kits");
  const techKitsList = document.getElementById("tech-kits-list");
  const techPaneAcc = document.getElementById("tech-pane-accessories");
  const accCategoryPills = document.getElementById("acc-category-pills");
  const accSearchFilter = document.getElementById("acc-search-filter");
  const techAccList = document.getElementById("tech-accessories-list");
  const techPaneUnits = document.getElementById("tech-pane-units");
  const techUnitsList = document.getElementById("tech-units-list");
  const techPaneVariants = document.getElementById("tech-pane-variants");
  const techVariantsList = document.getElementById("tech-variants-list");

  // State
  let currentZoom = 1.0;
  let currentPage = 1;
  let isDragging = false;
  let startX = 0, startY = 0;
  let scrollLeft = 0, scrollTop = 0;

  // -------------------------------------------------------------
  // EVENT LISTENERS
  // -------------------------------------------------------------
  searchBtn.addEventListener("click", () => executeSearch());

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      executeSearch();
    }
  });

  searchInput.addEventListener("input", () => {
    clearBtn.style.display = searchInput.value ? "block" : "none";
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    clearBtn.style.display = "none";
    searchInput.focus();
    resetToEmptyState();
  });

  // Preset Chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-query");
      searchInput.value = q;
      clearBtn.style.display = "block";
      executeSearch();
    });
  });

  // Filters Trigger
  brandFilter.addEventListener("change", () => { if (searchInput.value.trim()) executeSearch(); });
  categoryFilter.addEventListener("change", () => { if (searchInput.value.trim()) executeSearch(); });
  limitSelect.addEventListener("change", () => { if (searchInput.value.trim()) executeSearch(); });
  catalogOnlyToggle.addEventListener("change", () => { if (searchInput.value.trim()) executeSearch(); });

  // Modal Controls (PDF Viewer)
  modalCloseBtn.addEventListener("click", closeModal);
  pdfModal.addEventListener("click", (e) => {
    if (e.target === pdfModal) closeModal();
  });

  // Modal Controls (Tech / Compatibility / Kits Modal)
  techModalCloseBtn.addEventListener("click", closeTechModal);
  techModal.addEventListener("click", (e) => {
    if (e.target === techModal) closeTechModal();
  });

  // Tech Modal Tabs
  techTabBtnKits.addEventListener("click", () => switchTechTab("kits"));
  techTabBtnAcc.addEventListener("click", () => switchTechTab("accessories"));
  techTabBtnUnits.addEventListener("click", () => switchTechTab("units"));
  techTabBtnVariants.addEventListener("click", () => switchTechTab("variants"));

  // Global Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (pdfModal.style.display !== "none") {
        closeModal();
      } else if (techModal.style.display !== "none") {
        closeTechModal();
      }
    }
  });

  // Zoom & Pan
  zoomInBtn.addEventListener("click", () => adjustZoom(0.2));
  zoomOutBtn.addEventListener("click", () => adjustZoom(-0.2));
  zoomFitBtn.addEventListener("click", () => resetZoom());

  prevPageBtn.addEventListener("click", () => {
    if (currentPage > 1) openPdfViewer(currentPage - 1);
  });
  nextPageBtn.addEventListener("click", () => {
    if (currentPage < 1500) openPdfViewer(currentPage + 1);
  });

  // Drag to pan image
  imageViewport.addEventListener("mousedown", (e) => {
    if (e.target === pdfPageImg) {
      isDragging = true;
      imageViewport.style.cursor = "grabbing";
      startX = e.pageX - imageViewport.offsetLeft;
      startY = e.pageY - imageViewport.offsetTop;
      scrollLeft = imageViewport.scrollLeft;
      scrollTop = imageViewport.scrollTop;
    }
  });

  window.addEventListener("mouseup", () => {
    isDragging = false;
    imageViewport.style.cursor = "default";
  });

  imageViewport.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    e.preventDefault();
    const x = e.pageX - imageViewport.offsetLeft;
    const y = e.pageY - imageViewport.offsetTop;
    const walkX = (x - startX) * 1.5;
    const walkY = (y - startY) * 1.5;
    imageViewport.scrollLeft = scrollLeft - walkX;
    imageViewport.scrollTop = scrollTop - walkY;
  });

  // -------------------------------------------------------------
  // SEARCH EXECUTION
  // -------------------------------------------------------------
  async function executeSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    // Show loading
    emptyState.style.display = "none";
    resultsGrid.style.display = "none";
    loadingState.style.display = "block";
    diagnosticBar.style.display = "none";

    const params = new URLSearchParams({
      q: query,
      brand: brandFilter.value,
      category: categoryFilter.value,
      limit: limitSelect.value,
      catalog_only: catalogOnlyToggle.checked
    });

    try {
      const res = await fetch(`/api/search?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const data = await res.json();
      renderResults(data);
    } catch (err) {
      console.error("Search error:", err);
      loadingState.style.display = "none";
      alert("Errore durante la ricerca: " + err.message);
    }
  }

  function resetToEmptyState() {
    emptyState.style.display = "block";
    resultsGrid.style.display = "none";
    loadingState.style.display = "none";
    diagnosticBar.style.display = "none";
  }

  // -------------------------------------------------------------
  // RENDER RESULTS
  // -------------------------------------------------------------
  function renderResults(data) {
    loadingState.style.display = "none";

    // Diagnostic bar
    diagnosticBar.style.display = "flex";
    queryEcho.textContent = data.query || "";
    latencyVal.textContent = `${data.execution_time_ms || 0} ms`;
    countVal.textContent = data.total_results || 0;

    const isShortCircuit = data.match_type === "exact_code_short_circuit";
    matchBadge.className = `match-badge ${isShortCircuit ? "short-circuit" : "hybrid"}`;
    matchBadge.textContent = isShortCircuit ? "⚡ Exact Match O(1)" : "🧠 Hybrid Dense + BM25";

    if (data.detected_brand) {
      detectedBrandBadge.style.display = "inline-block";
      detectedBrandBadge.textContent = `Brand: ${data.detected_brand}`;
    } else {
      detectedBrandBadge.style.display = "none";
    }

    // Results Grid
    resultsGrid.innerHTML = "";
    if (!data.results || data.results.length === 0) {
      resultsGrid.style.display = "block";
      resultsGrid.innerHTML = `
        <div class="empty-state" style="padding: 40px 20px;">
          <div class="empty-icon">🔎</div>
          <h3>Nessun risultato trovato</h3>
          <p>Nessun articolo corrisponde alla query specificata. Prova a verificare il codice o usare termini più generici.</p>
        </div>
      `;
      return;
    }

    resultsGrid.style.display = "grid";
    data.results.forEach((item) => {
      const card = createProductCard(item);
      resultsGrid.appendChild(card);
    });
  }

  function renderCardBadges(item) {
    let html = `<span class="brand-badge">${escapeHtml(item.brand || "PUGLIA TERMICA")}</span>`;
    const catUpper = (item.category_path || item.category || "").toUpperCase();
    const nameUpper = (item.name || "").toUpperCase();

    // 0. Accessori e Componenti: MAI specifiche macchina o BTU
    const isAccessory = (
      item.is_accessory ||
      catUpper.includes("ACCESSORI") ||
      catUpper.includes("RICAMBI") ||
      ["GRIGLIA", "PANNELLO", "COMANDO", "TERMOSTATO", "FILTRO", "RACCORDO", "KIT SCARIC", "KIT FUMI", "KIT SDOPP", "KIT COASS", "KIT RACC", "KIT TUBI", "VALVOLA", "DIMA", "CONTROCASSA", "CASSA COPERTURA", "PIEDINI", "DEFLETTORE", "SONDA", "TAPPO", "BASETTA", "CAVO", "SCHEDA", "CENTRALINA", "MOTORE ELET", "BRUCIATORE", "DEUMIDIFICATORE", "ESTENS GARANZIA"].some(k => nameUpper.startsWith(k) || nameUpper.includes(" " + k))
    ) && !["VENTILCONV", "CALDAIA", "SCALDABAGNO", "CLIMATIZZATORE"].some(k => nameUpper.includes(k));

    if (isAccessory) {
      return html;
    }

    // 1. Scaldabagni
    if (item.is_scaldabagno || item.capacita_litri || item.tag_litri) {
      const litriVal = item.tag_litri || (item.capacita_litri ? item.capacita_litri + ' L' : null);
      if (litriVal) {
        html += `<span class="badge-litri">💧 ${escapeHtml(litriVal)}</span>`;
      }
      if (item.gas) {
        const gasClass = item.gas === 'METANO' ? 'gas-met' : 'gas-gpl';
        html += `<span class="badge-gas ${gasClass}">🔥 ${escapeHtml(item.gas)}</span>`;
      }
      if (item.camera) {
        const camLabel = item.camera === 'CAMERA_STAGNA' ? 'C/S Stagna' : (item.camera === 'CAMERA_APERTA' ? 'C/A Aperta' : item.camera.replace('_', ' '));
        html += `<span class="badge-camera">🚪 ${escapeHtml(camLabel)}</span>`;
      }
      return html;
    }

    // 2. Ventilconvettori (Fancoil) - SOLO se marcati o categoria ventilconvettori
    if (item.is_ventilconvettore || (item.tag_kw && catUpper.includes('VENTIL'))) {
      const kwVal = item.tag_kw || (item.kw_caldo ? `${item.kw_caldo} kW C / ${item.kw_freddo || ''} kW F` : (item.kw_freddo ? `${item.kw_freddo} kW F` : null));
      if (kwVal) {
        html += `<span class="badge-fancoil-kw">⚡ ${escapeHtml(kwVal)}</span>`;
      }
      if (item.taglia_modello) {
        html += `<span class="badge-model">🏷️ ${escapeHtml(item.taglia_modello)}</span>`;
      }
      return html;
    }

    // 3. Pompe di Calore & Sistemi Ibridi
    if (item.is_pompa_calore || catUpper.includes('POMPE DI CALORE')) {
      if (item.tag_kw) {
        html += `<span class="badge-pdc-kw">⚡ ${escapeHtml(item.tag_kw)}</span>`;
      }
      const litriVal = item.tag_litri || (item.litri ? item.litri + ' L' : null);
      if (litriVal) {
        html += `<span class="badge-litri">💧 ${escapeHtml(litriVal)}</span>`;
      }
      if (item.tubi) {
        html += `<span class="badge-tubi">⚙️ Tubi ${escapeHtml(item.tubi)}</span>`;
      }
      return html;
    }

    // 4. Caldaie (kW certificato, MAI BTU)
    if (item.is_boiler || (item.taglia_kw && !item.taglia_btu && nameUpper.includes('CALD'))) {
      const kwVal = item.tag_kw || (item.taglia_kw ? item.taglia_kw + ' kW' : null);
      if (kwVal) {
        html += `<span class="kw-tag">🔥 ${escapeHtml(kwVal)}</span>`;
      }
      return html;
    }

    // 5. Climatizzazione (PER LE UE LASCIA SEMPRE KW, PER LE UI SEMPRE BTU)
    if (item.tipo_unita === 'MONOBLOCCO_SUE' || item.is_monoblocco_sue) {
      const kwVal = item.tag_kw || (item.taglia_kw ? item.taglia_kw + ' kW' : null);
      html += `<span class="badge-sue">🔄 S/UE Monoblocco${kwVal ? ' · ' + escapeHtml(kwVal) : ''}</span>`;
      return html;
    }

    if (item.is_ue || item.tipo_unita === 'UE') {
      const kwVal = item.tag_kw || (item.taglia_kw ? item.taglia_kw + ' kW' : null);
      if (kwVal) {
        html += `<span class="kw-tag">🏢 UE · ${escapeHtml(kwVal)}</span>`;
      } else {
        html += `<span class="kw-tag">🏢 UE</span>`;
      }
      if (item.max_ui_collegabili && item.max_ui_collegabili > 1) {
        const sysLabel = item.max_ui_collegabili === 2 ? 'Dual (2 UI)' :
                         (item.max_ui_collegabili === 3 ? 'Trial (3 UI)' :
                         (item.max_ui_collegabili === 4 ? 'Quadri (4 UI)' :
                         (item.max_ui_collegabili === 5 ? 'Penta (5 UI)' : `${item.max_ui_collegabili} UI`)));
        html += `<span class="badge-ports">🔌 ${escapeHtml(sysLabel)}</span>`;
      } else if (item.tipo_sistema && item.tipo_sistema.includes('Mono')) {
        html += `<span class="badge-ports">🔌 Mono (1 UI)</span>`;
      }
      return html;
    }

    if (item.is_ui || item.tipo_unita === 'UI' || item.tag_btu || item.taglia_btu) {
      const btuVal = item.tag_btu_display || item.tag_btu || (item.taglia_btu ? item.taglia_btu + ' BTU' : null);
      if (btuVal) {
        html += `<span class="btu-tag">❄️ UI · ${escapeHtml(btuVal)}</span>`;
      } else {
        html += `<span class="btu-tag">❄️ UI</span>`;
      }
      return html;
    }

    if (item.taglia_kw) {
      const kwVal = item.tag_kw || (item.taglia_kw ? item.taglia_kw + ' kW' : null);
      if (kwVal) {
        html += `<span class="kw-tag">⚡ ${escapeHtml(kwVal)}</span>`;
      }
      return html;
    }

    return html;
  }

  function createProductCard(item) {
    const card = document.createElement("article");
    card.className = "product-card glass";

    const grossPrice = item.gross_price != null ? `${Number(item.gross_price).toFixed(2)} €` : "N/D";
    const netPrice = item.net_price != null ? `${Number(item.net_price).toFixed(2)} €` : "N/D";
    
    let discountBadgeHtml = "";
    if (item.gross_price && item.net_price && item.gross_price > item.net_price) {
      const disc = Math.round((1 - item.net_price / item.gross_price) * 100);
      discountBadgeHtml = `<span class="discount-badge">-${disc}%</span>`;
    }

    const hasPage = Boolean(item.primary_page);
    const pageText = hasPage ? `📖 Pagina ${item.primary_page}` : "Fuori Catalogo PDF";
    const kits = item.kits || [];
    const singleUnits = item.single_units || [];
    const variants = item.variants || [];
    const accessoryGroups = item.accessory_groups || [];
    const totalKits = item.total_kits_count != null ? item.total_kits_count : kits.length;
    const totalUnits = item.total_units_count != null ? item.total_units_count : singleUnits.length;
    const totalAccessories = item.total_accessories_count || 0;

    const matchedTableContext = item.matched_table_context || null;
    const primaryTableContext = item.table_context || null;
    const displayedTableContext = matchedTableContext || primaryTableContext || {};
    const displayedFamily = displayedTableContext.catalog_family || item.catalog_family || "";
    const displayedFamilyKey = displayedTableContext.family_key || item.family_key || "";
    const displayedTableTitle = displayedTableContext.table_title || item.table_title || displayedFamily;
    const displayedTablePage = displayedTableContext.page || item.table_page || "";
    const displayedTableSource = displayedTableContext.source || item.table_source || "";
    const primaryFamily = (primaryTableContext && primaryTableContext.catalog_family) || item.catalog_family || "";
    const isAlternateTableMatch = Boolean(
      matchedTableContext && primaryFamily && displayedFamily && primaryFamily !== displayedFamily
    );
    const familyConflict = primaryTableContext && primaryTableContext.family_conflict;
    const tableContextHtml = displayedFamily ? `
      <div class="family-context-panel ${isAlternateTableMatch ? 'alternate-match' : ''}">
        <div class="family-context-heading">
          <span class="family-context-label">Famiglia commerciale PDF</span>
          ${item.table_family_match === 'exact' ? '<span class="family-match-badge">Match tabella</span>' : ''}
        </div>
        <div class="family-context-main" title="${escapeHtml(displayedTableTitle)}">${escapeHtml(displayedFamily)}</div>
        <div class="family-context-meta">
          ${displayedFamilyKey ? `<code>${escapeHtml(displayedFamilyKey)}</code>` : ''}
          ${displayedTablePage ? `<span>Pagina ${escapeHtml(displayedTablePage)}</span>` : ''}
          ${displayedTableSource ? `<span>${escapeHtml(displayedTableSource)}</span>` : ''}
        </div>
        ${isAlternateTableMatch ? `
          <div class="family-context-note">Contesto primario: ${escapeHtml(primaryFamily)}</div>
        ` : ''}
        ${familyConflict ? `
          <div class="family-conflict-note">Conflitto nome/tabella segnalato</div>
        ` : ''}
      </div>
    ` : '';

    const isUe = item.is_ue || item.tipo_unita === "UE";
    const isUi = item.is_ui || item.tipo_unita === "UI";
    const unitLabel = isUe ? "❄️ UI Compatibili" : (isUi ? "🏢 UE Compatibili" : (item.product_type === "INDOOR_UNIT" ? "🏢 UE Abbinabili" : "❄️ UI Abbinabili"));

    // Card structure
    card.innerHTML = `
      <div>
        <div class="card-top">
          <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
            ${renderCardBadges(item)}
          </div>
          <span class="score-badge">Score: ${item.score || 0}</span>
        </div>

        <h3 class="product-name">${escapeHtml(item.name || "Articolo senza nome")}</h3>
        <p class="category-path" title="${escapeHtml(item.category || '')}">${escapeHtml(item.category || "Generale")}</p>

        ${tableContextHtml}

        <div class="codes-group">
          <div class="code-pill copy-btn" data-copy="${escapeHtml(item.code || '')}" title="Clicca per copiare">
            <span class="code-label">PT:</span>
            <span class="code-val">${escapeHtml(item.code || '-')}</span>
            <span class="copy-icon">📋</span>
          </div>
          ${item.mfg_code ? `
          <div class="code-pill copy-btn" data-copy="${escapeHtml(item.mfg_code)}" title="Clicca per copiare">
            <span class="code-label">MPN:</span>
            <span class="code-val">${escapeHtml(item.mfg_code)}</span>
            <span class="copy-icon">📋</span>
          </div>` : ''}
        </div>

        <div class="price-box">
          <div class="price-item">
            <span class="price-label">Listino Ufficiale</span>
            <span class="price-gross-val">${grossPrice}</span>
          </div>
          <div class="price-item" style="text-align: right;">
            <span class="price-label">Prezzo Riservato Netto</span>
            <span class="price-net-val">${netPrice}</span>
          </div>
          ${discountBadgeHtml}
        </div>
      </div>

      <div>
        <div class="card-actions">
          <button class="btn-view-page" ${!hasPage ? "disabled" : ""} data-page="${item.primary_page || 0}">
            <span>${pageText}</span>
          </button>
          ${totalKits > 0 ? `
          <button class="btn-kits open-tech-btn" data-tab="kits" title="Visualizza i ${totalKits} kit e combinazioni compatibili">
            <span>🧩 Kit Compatibili (${totalKits})</span>
          </button>` : ''}
          ${totalUnits > 0 ? `
          <button class="btn-units open-tech-btn" data-tab="units" title="Visualizza le ${totalUnits} singole unità compatibili">
            <span>${unitLabel} (${totalUnits})</span>
          </button>` : ''}
          ${totalAccessories > 0 ? `
          <button class="btn-accessories open-tech-btn" data-tab="accessories" title="Visualizza i ${totalAccessories} accessori tecnici compatibili">
            <span>📦 Accessori (${totalAccessories})</span>
          </button>` : ''}
          ${variants.length > 0 ? `
          <button class="btn-variants open-tech-btn" data-tab="variants" title="Visualizza le ${variants.length} altre potenze/taglie">
            <span>🔄 Taglie (${variants.length})</span>
          </button>` : ''}
        </div>
      </div>
    `;

    // Click to copy codes
    card.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const textToCopy = btn.getAttribute("data-copy");
        if (textToCopy) {
          navigator.clipboard.writeText(textToCopy);
          showToast(`Copiato: ${textToCopy}`);
        }
      });
    });

    // View PDF page button
    const viewBtn = card.querySelector(".btn-view-page");
    if (viewBtn && hasPage) {
      viewBtn.addEventListener("click", () => {
        openPdfViewer(item.primary_page);
      });
    }

    // Open Tech Modal buttons (Kits, Accessories, Units, Variants)
    card.querySelectorAll(".open-tech-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const tab = btn.getAttribute("data-tab") || "accessories";
        openTechModal(item, tab);
      });
    });

    return card;
  }

  // -------------------------------------------------------------
  // TECH / COMPATIBILITY / KITS MODAL LOGIC
  // -------------------------------------------------------------
  let currentModalItem = null;

  function openTechModal(item, defaultTab = "kits") {
    currentModalItem = item;

    const kits = item.kits || [];
    const singleUnits = item.single_units || [];
    const variants = item.variants || [];
    const accessoryGroups = item.accessory_groups || [];
    const totalKits = item.total_kits_count != null ? item.total_kits_count : kits.length;
    const totalUnits = item.total_units_count != null ? item.total_units_count : singleUnits.length;
    const totalAccessories = item.total_accessories_count || 0;

    // Header info
    techModalBrand.textContent = item.brand || "PUGLIA TERMICA";
    const modalTableContext = item.matched_table_context || item.table_context || {};
    const modalFamily = modalTableContext.catalog_family || item.catalog_family || "";
    const modalFamilyKey = modalTableContext.family_key || item.family_key || "";
    const modalTablePage = modalTableContext.page || item.table_page || "";
    const modalTableSource = modalTableContext.source || item.table_source || "";
    if (modalFamily) {
      techModalFamily.style.display = "inline-flex";
      techModalFamily.textContent = `Famiglia PDF: ${modalFamily}`;
      techModalFamily.title = [modalFamilyKey, modalTablePage ? `Pagina ${modalTablePage}` : "", modalTableSource]
        .filter(Boolean)
        .join(" · ");
    } else {
      techModalFamily.style.display = "none";
      techModalFamily.textContent = "";
      techModalFamily.title = "";
    }
    techModalTitle.textContent = item.name || "Articolo";
    techModalPtVal.textContent = item.code || "-";
    techModalPtPill.setAttribute("data-copy", item.code || "");

    const modalCatUpper = (item.category_path || item.category || "").toUpperCase();
    const modalNameUpper = (item.name || "").toUpperCase();
    const modalIsAccessory = (
      item.is_accessory ||
      modalCatUpper.includes("ACCESSORI") ||
      modalCatUpper.includes("RICAMBI") ||
      ["GRIGLIA", "PANNELLO", "COMANDO", "TERMOSTATO", "FILTRO", "RACCORDO", "KIT SCARIC", "KIT FUMI", "KIT SDOPP", "KIT COASS", "KIT RACC", "KIT TUBI", "VALVOLA", "DIMA", "CONTROCASSA", "CASSA COPERTURA", "PIEDINI", "DEFLETTORE", "SONDA", "TAPPO", "BASETTA", "CAVO", "SCHEDA", "CENTRALINA", "MOTORE ELET", "BRUCIATORE", "DEUMIDIFICATORE", "ESTENS GARANZIA"].some(k => modalNameUpper.startsWith(k) || modalNameUpper.includes(" " + k))
    ) && !["VENTILCONV", "CALDAIA", "SCALDABAGNO", "CLIMATIZZATORE"].some(k => modalNameUpper.includes(k));

    if (modalIsAccessory) {
      techModalBtu.style.display = "none";
    } else if (item.is_scaldabagno || item.capacita_litri || item.tag_litri) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "badge-litri";
      techModalBtu.textContent = `💧 ${item.tag_litri || item.capacita_litri + ' L'}${item.gas ? ' | ' + item.gas : ''}`;
    } else if (item.is_ventilconvettore || (item.tag_kw && modalCatUpper.includes('VENTIL'))) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "badge-fancoil-kw";
      const fancoilKw = item.tag_kw || (item.kw_caldo && item.kw_freddo ? `${item.kw_caldo} kW C / ${item.kw_freddo} kW F` : (item.kw_caldo ? `${item.kw_caldo} kW C` : (item.kw_freddo ? `${item.kw_freddo} kW F` : '')));
      techModalBtu.textContent = `⚡ ${fancoilKw}`;
    } else if (item.is_pompa_calore || modalCatUpper.includes('POMPE DI CALORE')) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "badge-pdc-kw";
      techModalBtu.textContent = `⚡ ${item.tag_kw || 'PDC'}`;
    } else if (item.is_boiler || (item.taglia_kw && !item.taglia_btu && modalNameUpper.includes('CALD'))) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "kw-tag";
      techModalBtu.textContent = `🔥 ${item.tag_kw || item.taglia_kw + ' kW'}`;
    } else if (item.tipo_unita === 'MONOBLOCCO_SUE' || item.is_monoblocco_sue) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "badge-sue";
      techModalBtu.textContent = `🔄 S/UE Monoblocco${item.tag_kw ? ' · ' + item.tag_kw : ''}`;
    } else if (item.is_ue || item.tipo_unita === 'UE') {
      // PER LE UE SEMPRE KW
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "kw-tag";
      techModalBtu.textContent = `🏢 UE · ${item.tag_kw || (item.taglia_kw ? item.taglia_kw + ' kW' : 'Unità Esterna')}`;
    } else if (item.is_ui || item.tipo_unita === 'UI' || item.tag_btu || item.taglia_btu) {
      // PER LE UI SEMPRE BTU
      const btuTagText = item.tag_btu_display || item.tag_btu || (item.taglia_btu ? item.taglia_btu + ' BTU' : null);
      if (btuTagText) {
        techModalBtu.style.display = "inline-flex";
        techModalBtu.className = "btu-tag";
        techModalBtu.textContent = `❄️ UI · ${btuTagText}`;
      } else {
        techModalBtu.style.display = "inline-flex";
        techModalBtu.className = "btu-tag";
        techModalBtu.textContent = `❄️ UI`;
      }
    } else if (item.taglia_kw) {
      techModalBtu.style.display = "inline-flex";
      techModalBtu.className = "kw-tag";
      techModalBtu.textContent = `⚡ ${item.tag_kw || item.taglia_kw + ' kW'}`;
    } else {
      techModalBtu.style.display = "none";
    }

    if (item.mfg_code) {
      techModalMfgPill.style.display = "inline-flex";
      techModalMfgVal.textContent = item.mfg_code;
      techModalMfgPill.setAttribute("data-copy", item.mfg_code);
    } else {
      techModalMfgPill.style.display = "none";
    }

    techModalGross.textContent = item.gross_price != null ? `${Number(item.gross_price).toFixed(2)} €` : "-";
    techModalNet.textContent = item.net_price != null ? `${Number(item.net_price).toFixed(2)} €` : "-";

    if (item.primary_page) {
      techModalViewPdfBtn.style.display = "inline-flex";
      techModalViewPdfBtn.textContent = `📖 Pagina ${item.primary_page}`;
      techModalViewPdfBtn.onclick = () => {
        closeTechModal();
        openPdfViewer(item.primary_page);
      };
    } else {
      techModalViewPdfBtn.style.display = "none";
    }

    // Tab counts & visibility
    techTabCountKits.textContent = totalKits;
    techTabBtnKits.style.display = totalKits > 0 ? "inline-flex" : "none";

    techTabCountAcc.textContent = totalAccessories;
    techTabBtnAcc.style.display = totalAccessories > 0 ? "inline-flex" : "none";

    const isModalUe = item.is_ue || item.tipo_unita === "UE";
    const isModalUi = item.is_ui || item.tipo_unita === "UI";

    techTabCountUnits.textContent = totalUnits;
    techTabBtnUnits.style.display = totalUnits > 0 ? "inline-flex" : "none";
    techTabLabelUnits.textContent = isModalUe ? `❄️ Unità Interne (${totalUnits})` : (isModalUi ? `🏢 Unità Esterne (${totalUnits})` : (item.product_type === "INDOOR_UNIT" ? `🏢 Unità Esterne (${totalUnits})` : `❄️ Unità Interne (${totalUnits})`));

    techTabCountVariants.textContent = variants.length;
    techTabBtnVariants.style.display = variants.length > 0 ? "inline-flex" : "none";

    // Decide which tab to open
    let targetTab = defaultTab;
    if (targetTab === "kits" && totalKits === 0) {
      targetTab = totalAccessories > 0 ? "accessories" : (totalUnits > 0 ? "units" : "variants");
    } else if (targetTab === "accessories" && totalAccessories === 0) {
      targetTab = totalKits > 0 ? "kits" : (totalUnits > 0 ? "units" : "variants");
    } else if (targetTab === "units" && totalUnits === 0) {
      targetTab = totalKits > 0 ? "kits" : (totalAccessories > 0 ? "accessories" : "variants");
    } else if (targetTab === "variants" && variants.length === 0) {
      targetTab = totalKits > 0 ? "kits" : (totalAccessories > 0 ? "accessories" : "units");
    }

    // Render contents
    renderModalKits(kits);
    renderModalAccessories(accessoryGroups, totalAccessories);
    renderModalUnits(singleUnits, item.product_type, item);
    renderModalVariants(variants);

    // Switch tab
    switchTechTab(targetTab);

    // Open modal
    techModal.style.display = "flex";
    document.body.style.overflow = "hidden";
  }

  function closeTechModal() {
    techModal.style.display = "none";
    if (pdfModal.style.display === "none") {
      document.body.style.overflow = "auto";
    }
  }

  function switchTechTab(tabName) {
    techTabBtnKits.classList.toggle("active", tabName === "kits");
    techTabBtnAcc.classList.toggle("active", tabName === "accessories");
    techTabBtnUnits.classList.toggle("active", tabName === "units");
    techTabBtnVariants.classList.toggle("active", tabName === "variants");

    techPaneKits.style.display = tabName === "kits" ? "flex" : "none";
    techPaneAcc.style.display = tabName === "accessories" ? "flex" : "none";
    techPaneUnits.style.display = tabName === "units" ? "flex" : "none";
    techPaneVariants.style.display = tabName === "variants" ? "flex" : "none";
  }

  function renderModalKits(kits) {
    if (!kits || kits.length === 0) {
      techKitsList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">Nessun kit pre-configurato a catalogo per questo modello.</div>`;
      return;
    }

    techKitsList.innerHTML = kits.map(kit => `
      <div class="tech-kit-card">
        <div class="tech-kit-top">
          <div class="tech-kit-badges">
            <span class="kit-conf-tag">🧩 ${escapeHtml(kit.configuration || 'Kit Clima')}</span>
            <span class="acc-brand-tag">${escapeHtml(kit.brand || '')}</span>
            ${kit.badge_text ? `<span class="acc-compat-badge official">${escapeHtml(kit.badge_text)}</span>` : ''}
          </div>
          <div class="tech-kit-price-box">
            <span style="font-size:0.7rem; color:var(--text-muted); text-transform:uppercase;">Totale Kit Netto</span>
            <span class="tech-kit-net">${kit.net_price ? Number(kit.net_price).toFixed(2) + ' €' : '-'}</span>
          </div>
        </div>
        <div class="tech-kit-title">${escapeHtml(kit.name)}</div>
        ${kit.catalog_note ? `<div class="acc-catalog-note" style="margin-top: 2px;">📄 <em>${escapeHtml(kit.catalog_note)}</em></div>` : ''}
        
        ${kit.ui_components && kit.ui_components.length > 0 ? `
          <div class="tech-kit-components">
            <span class="kit-components-label">${escapeHtml(kit.components_label || (kit.is_boiler_kit ? 'Componenti Inclusi nel Kit di Installazione:' : 'Unità Interne Incluse nel Bundle:'))}</span>
            ${kit.ui_components.map(comp => `
              <div class="tech-kit-comp-row">
                <div class="tech-kit-comp-info">
                  <span class="tech-kit-comp-code copy-btn" data-copy="${escapeHtml(comp.code || '')}" title="Copia codice PT">${escapeHtml(comp.code || '-')}</span>
                  <span class="tech-kit-comp-name" title="${escapeHtml(comp.name)}">${escapeHtml(comp.name)}</span>
                  ${comp.component_type === 'CALDAIA' ? 
                    `<span class="kw-tag kw-tag-sm">🔥 ${escapeHtml(comp.tag_btu || 'Caldaia')}</span>` :
                    (comp.component_type === 'DEFANGATORE' ?
                      `<span class="badge-litri badge-sm">🛡️ ${escapeHtml(comp.tag_btu || 'Defangatore 3/4"')}</span>` :
                      (comp.component_type && comp.component_type.startsWith('FUMISTERIA') ?
                        `<span class="badge-fancoil-kw badge-sm">💨 ${escapeHtml(comp.tag_btu || 'Fumi')}</span>` :
                        (comp.tag_btu ? `<span class="btu-tag btu-tag-sm">${escapeHtml(comp.tag_btu)}</span>` : (comp.taglia_btu ? `<span class="btu-tag btu-tag-sm">${escapeHtml(comp.taglia_btu + ' btu')}</span>` : ''))
                      )
                    )
                  }
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="tech-kit-comp-price">${comp.net_price ? Number(comp.net_price).toFixed(2) + ' €' : '-'}</span>
                  <button class="kit-chip-search search-code-btn" data-code="${escapeHtml(comp.code || '')}" title="Cerca questo componente">🔍</button>
                </div>
              </div>
            `).join('')}
          </div>
        ` : ''}

        <div class="tech-kit-footer">
          <div class="code-pill copy-btn" data-copy="${escapeHtml(kit.code)}" title="Copia codice kit">
            <span class="code-label">${kit.is_boiler_kit ? 'Codici Kit:' : 'Bundle:'}</span>
            <span class="code-val">${escapeHtml(kit.code)}</span>
            <span class="copy-icon">📋</span>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="acc-search-btn search-code-btn" data-code="${escapeHtml(kit.code.split('+')[0])}" title="Visualizza dettagli">${kit.is_boiler_kit ? 'Dettagli Caldaia →' : 'Visualizza Bundle →'}</button>
            ${kit.catalog_page ? `<button class="acc-page-btn view-page-btn" data-page="${kit.catalog_page}" title="Pagina Catalogo">📖 P.${kit.catalog_page}</button>` : ''}
          </div>
        </div>
      </div>
    `).join('');

    attachModalActions(techKitsList);
  }

  function renderModalAccessories(groups, totalCount) {
    if (!groups || groups.length === 0) {
      accCategoryPills.innerHTML = "";
      techAccList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">Nessun accessorio tecnico compatibile trovato a catalogo.</div>`;
      return;
    }

    let activeCat = "ALL";
    let filterQuery = "";

    // Generate Category Pills
    accCategoryPills.innerHTML = `
      <button class="acc-category-pill active" data-cat="ALL">Tutti (${totalCount})</button>
      ${groups.map(g => `
        <button class="acc-category-pill" data-cat="${escapeHtml(g.group_name || '')}">
          ${g.icon || '📦'} ${escapeHtml(g.group_name || 'Altro')} (${g.items.length})
        </button>
      `).join('')}
    `;

    // Category click handler
    accCategoryPills.querySelectorAll(".acc-category-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        accCategoryPills.querySelectorAll(".acc-category-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeCat = pill.getAttribute("data-cat");
        renderFiltered();
      });
    });

    // Reset search filter input
    accSearchFilter.value = "";
    accSearchFilter.oninput = (e) => {
      filterQuery = e.target.value.toLowerCase().trim();
      renderFiltered();
    };

    function renderFiltered() {
      let filteredGroups = groups;
      if (activeCat !== "ALL") {
        filteredGroups = groups.filter(g => g.group_name === activeCat);
      }

      let renderedAny = false;
      let html = "";

      filteredGroups.forEach(group => {
        let items = group.items;
        if (filterQuery) {
          items = items.filter(it => 
            (it.name && it.name.toLowerCase().includes(filterQuery)) ||
            (it.code && it.code.toLowerCase().includes(filterQuery)) ||
            (it.brand && it.brand.toLowerCase().includes(filterQuery)) ||
            (it.catalog_note && it.catalog_note.toLowerCase().includes(filterQuery))
          );
        }

        if (items.length > 0) {
          renderedAny = true;
          html += `
            <div class="accessory-group-card">
              <div class="group-header">
                <span>${group.icon || '📦'}</span>
                <span>${escapeHtml(group.group_name || 'Accessori')}</span>
                <span class="badge-count" style="margin-left: auto;">${items.length}</span>
              </div>
              <div class="group-items-list">
                ${items.map(acc => `
                  <div class="accessory-row">
                    <div class="acc-info">
                      <div class="acc-title-line">
                        <span class="acc-brand-tag">${escapeHtml(acc.brand || '')}</span>
                        <span class="accessory-name" title="${escapeHtml(acc.name)}">${escapeHtml(acc.name)}</span>
                      </div>
                      ${acc.badge_text ? `<div class="acc-compat-badge ${acc.compatibility_level || ''}">${escapeHtml(acc.badge_text)}</div>` : ''}
                      ${acc.catalog_note ? `<div class="acc-catalog-note" title="${escapeHtml(acc.catalog_note)}">📄 <em>${escapeHtml(acc.catalog_note)}</em></div>` : ''}
                    </div>
                    <div class="acc-actions">
                      <div class="acc-price-block">
                        <span class="acc-price">${acc.net_price ? Number(acc.net_price).toFixed(2) + ' €' : '-'}</span>
                      </div>
                      <div class="acc-actions-btns">
                        <button class="acc-search-btn search-code-btn" data-code="${escapeHtml(acc.code)}" title="Cerca questo accessorio">${escapeHtml(acc.code)} →</button>
                        ${acc.catalog_page ? `<button class="acc-page-btn view-page-btn" data-page="${acc.catalog_page}" title="Visualizza catalogo a pag. ${acc.catalog_page}">📖 P.${acc.catalog_page}</button>` : ''}
                      </div>
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        }
      });

      if (!renderedAny) {
        techAccList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">Nessun accessorio trovato con i filtri selezionati.</div>`;
      } else {
        techAccList.innerHTML = html;
        attachModalActions(techAccList);
      }
    }

    renderFiltered();
  }

  function renderModalUnits(units, productType, currentItem) {
    if (!units || units.length === 0) {
      techUnitsList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">Nessuna unità specifica presente nelle tabelle combinazioni.</div>`;
      return;
    }

    const isCurrentUe = currentItem && (currentItem.is_ue || currentItem.tipo_unita === "UE");
    let bannerHtml = "";

    if (isCurrentUe) {
      const maxUi = currentItem.max_ui_collegabili || currentItem.porte_attacchi || 1;
      const sysType = currentItem.tipo_sistema || (maxUi > 1 ? `Multi-Split (${maxUi} UI)` : 'Mono-Split');
      const combPage = currentItem.catalog_combination_page;
      const tableName = currentItem.nome_tabella_combinazioni || (combPage ? `Tabella Combinazioni a Pagina ${combPage}` : 'Tabella Combinazioni Ufficiale');
      const combos = currentItem.combinazioni_ammesse || [];

      bannerHtml = `
        <div class="ue-comb-banner">
          <div class="ue-comb-banner-header">
            <div class="ue-comb-title">
              <span>🏢 Capacità di Connessione:</span>
              <span style="color: #38bdf8;">Fino a ${maxUi} Unità Interne (${escapeHtml(sysType)})</span>
            </div>
            ${combPage ? `
              <div class="ue-comb-ref">
                <span>📖 Tabella Catalogo Pag. ${combPage}</span>
                <button class="acc-page-btn view-page-btn" data-page="${combPage}" title="Apri tabella combinazioni nel catalogo">Apri Tabella P.${combPage} ↗</button>
              </div>
            ` : ''}
          </div>
          <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 4px;">
            ${escapeHtml(tableName)}: di seguito tutte le unità interne ufficialmente compatibili e abbinabili a catalogo.
          </div>
          ${combos.length > 0 ? `
            <div style="margin-top: 8px;">
              <span style="font-size: 0.74rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700;">Esempi di Combinazioni Ammesse dal Costruttore:</span>
              <div class="ue-comb-chips">
                ${combos.slice(0, 10).map(cb => `<span class="ue-comb-chip">⚡ ${escapeHtml(cb)}</span>`).join('')}
                ${combos.length > 10 ? `<span class="ue-comb-chip" style="background:rgba(255,255,255,0.06); color:var(--text-muted);">+altre ${combos.length - 10} combinazioni</span>` : ''}
              </div>
            </div>
          ` : ''}
        </div>
      `;
    }

    const cardsHtml = units.map(unit => {
      const isUnitUe = unit.is_outdoor_unit || unit.is_ue || (!unit.taglia_btu && (unit.taglia_kw || unit.tag_kw));
      const badgeHtml = isUnitUe ?
        `<span class="kw-tag">🏢 UE · ${escapeHtml(unit.tag_kw || unit.taglia_kw + ' kW')}</span>` :
        `<span class="btu-tag">❄️ UI · ${escapeHtml(unit.tag_btu_display || unit.tag_btu || (unit.taglia_btu ? unit.taglia_btu + ' BTU' : 'UI'))}</span>`;

      const subBadgeHtml = isUnitUe ?
        (unit.tipo_sistema ? `<span class="badge-ports">${escapeHtml(unit.tipo_sistema)}</span>` : '') :
        (unit.badge_text ? `<span class="acc-compat-badge official">${escapeHtml(unit.badge_text)}</span>` : '');

      return `
        <div class="tech-unit-card">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
              <span class="brand-badge" style="font-size:0.7rem;">${escapeHtml(unit.brand || "")}</span>
              ${badgeHtml}
              ${subBadgeHtml}
            </div>
          </div>
          <div class="tech-kit-title" style="margin-top:6px;">${escapeHtml(unit.name || "")}</div>
          ${unit.catalog_note ? `<div class="acc-catalog-note" style="margin-top: 2px;">📄 <em>${escapeHtml(unit.catalog_note)}</em></div>` : ''}
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
            <div class="code-pill copy-btn" data-copy="${escapeHtml(unit.code)}" title="Copia codice PT">
              <span class="code-label">PT:</span>
              <span class="code-val">${escapeHtml(unit.code)}</span>
              <span class="copy-icon">📋</span>
            </div>
            ${unit.mfg_code ? `
              <div class="code-pill copy-btn" data-copy="${escapeHtml(unit.mfg_code)}" title="Copia codice fornitore">
                <span class="code-label">MPN:</span>
                <span class="code-val">${escapeHtml(unit.mfg_code)}</span>
                <span class="copy-icon">📋</span>
              </div>
            ` : ''}
            <span class="tech-kit-net">${unit.net_price ? Number(unit.net_price).toFixed(2) + ' €' : '-'}</span>
          </div>
          <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:8px;">
            <button class="acc-search-btn search-code-btn" data-code="${escapeHtml(unit.code)}" title="Cerca questa unità">${escapeHtml(unit.code)} →</button>
            ${unit.catalog_page ? `<button class="acc-page-btn view-page-btn" data-page="${unit.catalog_page}" title="Pagina Catalogo">📖 P.${unit.catalog_page}</button>` : ''}
          </div>
        </div>
      `;
    }).join('');

    techUnitsList.innerHTML = bannerHtml + cardsHtml;
    attachModalActions(techUnitsList);
  }

  function renderModalVariants(variants) {
    if (!variants || variants.length === 0) {
      techVariantsList.innerHTML = `<div class="empty-state" style="padding: 24px; text-align: center; color: var(--text-muted);">Nessuna variante di potenza alternativa correlata.</div>`;
      return;
    }

    techVariantsList.innerHTML = variants.map(v => `
      <div class="variant-row">
        <span class="variant-name" title="${escapeHtml(v.name)}">${escapeHtml(v.name)}</span>
        <span class="variant-price">${v.net_price ? Number(v.net_price).toFixed(2) + ' €' : '-'}</span>
        <button class="acc-search-btn search-code-btn" data-code="${escapeHtml(v.code)}" title="Cerca questo modello">${escapeHtml(v.code)} →</button>
      </div>
    `).join('');

    attachModalActions(techVariantsList);
  }

  function attachModalActions(container) {
    // Copy buttons
    container.querySelectorAll(".copy-btn").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const textToCopy = btn.getAttribute("data-copy");
        if (textToCopy) {
          navigator.clipboard.writeText(textToCopy);
          showToast(`Copiato: ${textToCopy}`);
        }
      };
    });

    // Direct search for code
    container.querySelectorAll(".search-code-btn").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const code = btn.getAttribute("data-code");
        if (code) {
          closeTechModal();
          searchInput.value = code;
          clearBtn.style.display = "block";
          executeSearch();
        }
      };
    });

    // Direct open PDF page
    container.querySelectorAll(".view-page-btn").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const pageNum = btn.getAttribute("data-page");
        if (pageNum) {
          closeTechModal();
          openPdfViewer(pageNum);
        }
      };
    });
  }

  // -------------------------------------------------------------
  // PDF VIEWER MODAL LOGIC
  // -------------------------------------------------------------
  async function openPdfViewer(pageNum) {
    currentPage = Number(pageNum);
    modalPageNum.textContent = currentPage;
    sidebarPageNum.textContent = currentPage;
    pageIndicator.textContent = `Pag. ${currentPage}`;
    
    pdfModal.style.display = "flex";
    document.body.style.overflow = "hidden"; // block background scroll

    resetZoom();

    // Show image spinner
    imageSpinner.style.display = "block";
    pdfPageImg.style.display = "none";
    sidebarProductsList.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem;">Caricamento elenco prodotti...</p>`;

    // 1. Fetch image
    const imgUrl = `/api/page-image/${currentPage}?dpi=150&t=${Date.now()}`;
    const preload = new Image();
    preload.onload = () => {
      pdfPageImg.src = imgUrl;
      imageSpinner.style.display = "none";
      pdfPageImg.style.display = "block";
    };
    preload.onerror = () => {
      imageSpinner.innerHTML = `<p style="color: var(--accent-rose);">Errore nel rendering della pagina ${currentPage}</p>`;
    };
    preload.src = imgUrl;

    // 2. Fetch page summary for sidebar
    try {
      const sumRes = await fetch(`/api/page-summary/${currentPage}`);
      if (sumRes.ok) {
        const sumData = await sumRes.json();
        renderSidebarProducts(sumData.products || []);
      }
    } catch (e) {
      console.warn("Sidebar summary error:", e);
    }
  }

  function renderSidebarProducts(products) {
    sidebarCount.textContent = `${products.length} articoli`;
    if (products.length === 0) {
      sidebarProductsList.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem;">Nessun prodotto censito per questa pagina.</p>`;
      return;
    }

    sidebarProductsList.innerHTML = products.map(p => `
      <div class="sidebar-item">
        <div class="sidebar-item-top">
          <span class="sidebar-item-brand">${escapeHtml(p.brand || '')}</span>
          <span class="sidebar-item-code">${escapeHtml(p.code)}</span>
        </div>
        <div class="sidebar-item-name">${escapeHtml(p.name)}</div>
        <div class="sidebar-item-bottom">
          <span class="sidebar-item-price">${p.gross_price ? Number(p.gross_price).toFixed(2) + ' €' : '-'}</span>
          <span class="sidebar-item-mfg">${p.mfg_code ? 'MPN: ' + escapeHtml(p.mfg_code) : ''}</span>
        </div>
      </div>
    `).join('');
  }

  function closeModal() {
    pdfModal.style.display = "none";
    document.body.style.overflow = "auto";
  }

  function adjustZoom(delta) {
    currentZoom = Math.max(0.5, Math.min(3.5, currentZoom + delta));
    applyZoom();
  }

  function resetZoom() {
    currentZoom = 1.0;
    applyZoom();
    imageViewport.scrollLeft = 0;
    imageViewport.scrollTop = 0;
  }

  function applyZoom() {
    pdfPageImg.style.transform = `scale(${currentZoom})`;
    zoomLevel.textContent = `${Math.round(currentZoom * 100)}%`;
  }

  // -------------------------------------------------------------
  // TOAST NOTIFICATIONS
  // -------------------------------------------------------------
  function showToast(msg) {
    const toast = document.createElement("div");
    toast.className = "toast-msg";
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});
