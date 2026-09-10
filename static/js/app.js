(function () {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("zipfile");
  const fileLabel = document.getElementById("file-label");

  if (dropzone && fileInput && fileLabel) {
    const setName = () => {
      if (fileInput.files && fileInput.files[0]) {
        fileLabel.textContent = fileInput.files[0].name;
      }
    };
    fileInput.addEventListener("change", setName);

    ["dragenter", "dragover"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.add("is-drag");
      });
    });
    ["dragleave", "drop"].forEach((evt) => {
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.remove("is-drag");
      });
    });
    dropzone.addEventListener("drop", (e) => {
      const files = e.dataTransfer && e.dataTransfer.files;
      if (files && files.length) {
        fileInput.files = files;
        setName();
      }
    });
  }

  // Tabs
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const id = tab.dataset.tab;
      tabs.forEach((t) => {
        t.classList.toggle("is-active", t === tab);
        t.setAttribute("aria-selected", t === tab ? "true" : "false");
      });
      panels.forEach((p) => {
        const active = p.dataset.panel === id;
        p.classList.toggle("is-active", active);
        if (active) p.removeAttribute("hidden");
        else p.setAttribute("hidden", "");
      });
      applyFilters();
    });
  });

  // Other sub-tabs
  const chips = document.querySelectorAll(".chip");
  const otherPanels = document.querySelectorAll(".other-panel");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const id = chip.dataset.other;
      chips.forEach((c) => c.classList.toggle("is-active", c === chip));
      otherPanels.forEach((p) => {
        p.classList.toggle("is-active", p.dataset.otherPanel === id);
      });
      applyFilters();
    });
  });

  const search = document.getElementById("search");
  const sort = document.getElementById("sort");

  function parseDate(value) {
    if (!value) return 0;
    const t = Date.parse(value);
    return Number.isNaN(t) ? 0 : t;
  }

  function applyFilters() {
    const q = (search && search.value ? search.value : "").trim().toLowerCase();
    const mode = sort ? sort.value : "newest";
    const activePanel =
      document.querySelector(".tab-panel.is-active") ||
      document.querySelector('.tab-panel:not([hidden])');
    if (!activePanel) return;

    const lists = activePanel.querySelectorAll("[data-list]");
    lists.forEach((list) => {
      // Only filter visible other-panel lists when on "other"
      const parentOther = list.closest(".other-panel");
      if (parentOther && !parentOther.classList.contains("is-active")) return;

      const items = Array.from(list.querySelectorAll("li"));
      items.forEach((li) => {
        const name = (li.dataset.username || "").toLowerCase();
        li.classList.toggle("is-hidden", Boolean(q) && !name.includes(q));
      });

      const visible = items.filter((li) => !li.classList.contains("is-hidden"));
      visible.sort((a, b) => {
        const na = a.dataset.username || "";
        const nb = b.dataset.username || "";
        if (mode === "az") return na.localeCompare(nb);
        if (mode === "za") return nb.localeCompare(na);
        const da = parseDate(a.dataset.date);
        const db = parseDate(b.dataset.date);
        if (mode === "oldest") return da - db;
        return db - da;
      });
      visible.forEach((li) => list.appendChild(li));
    });
  }

  if (search) search.addEventListener("input", applyFilters);
  if (sort) sort.addEventListener("change", applyFilters);
})();
