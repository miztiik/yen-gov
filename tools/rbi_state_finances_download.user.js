// ==UserScript==
// @name         yen-gov - RBI State Finances (Study of Budgets) bulk stager
// @namespace    yen-gov
// @version      1.0.0
// @description  Config-driven BULK downloader for the RBI "State Finances: A Study of Budgets" publication - the canonical record of HOW state governments raise and spend money. Grabs EVERY data table (Appendix Tables, Statements, and Appendices I-IV: Revenue Receipts / Revenue Expenditure / Capital Receipts / Capital Expenditure) plus the narrative chapter PDFs, across all archive editions (2002-2026). Modern .xlsx, legacy .xls (2016 and earlier), and .pdf are all captured - the sibling Handbook stager taught us RBI serves old editions as .xls, and 2002-2005 here exist ONLY as PDF. Runs inside your own trusted RBI browser session (the F5 anti-bot CAPTCHA is already satisfied - nothing is bypassed). Reads each file's link + RBI caption + section LIVE from the page, auto-detects the single-year edition, validates each file is a real workbook/PDF (ZIP / OLE2 / %PDF magic), and saves it under <year>/<section>/<NNN>_<rbi-name>.<ext>. "Download ALL editions" sweeps every archive year in one click. Controls in the Tampermonkey menu.
// @author       yen-gov
// @updateURL    https://raw.githubusercontent.com/miztiik/yen-gov/main/tools/rbi_state_finances_download.user.js
// @downloadURL  https://raw.githubusercontent.com/miztiik/yen-gov/main/tools/rbi_state_finances_download.user.js
// @match        https://www.rbi.org.in/*
// @match        https://rbidocs.rbi.org.in/*
// @connect      rbidocs.rbi.org.in
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @grant        GM_registerMenuCommand
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_openInTab
// @run-at       document-idle
// @noframes
// ==/UserScript==

/*
 * SIBLING of tools/rbi_handbook_download.user.js. Same engine, same trusted-
 * session model, same "nothing is bypassed" stance - aimed at the OTHER RBI
 * publication the yen-gov data spine needs: the state budgets.
 *
 * WHY this publication:
 *   "State Finances: A Study of Budgets" is the single richest public source
 *   on Indian sub-national public finance - per-state revenue receipts,
 *   revenue expenditure, capital receipts, capital expenditure, deficits,
 *   debt, devolution and grants, year after year. It is exactly the "where
 *   does the money go" evidence base. We collect ALL of it now and let
 *   Hans + Max decide downstream which tables become indicators; a few
 *   overlapping or near-duplicate tables across editions are fine.
 *
 * WHAT it grabs (config-driven, see CONFIG):
 *   - SPREADSHEETS (.xlsx + .xls): the machine-readable data tables. This is
 *     the priority payload. 2016 and earlier are legacy .xls; 2017+ are .xlsx.
 *   - PDFs (.pdf): the narrative chapters (Overview, Fiscal Position, ...) AND
 *     a PDF twin of every data table. For 2002-2005 the PDFs are the ONLY
 *     form the data exists in (no spreadsheets were published).
 *   Both are ON by default ("collect all, decide later"). For a fast,
 *   data-only pass set GRAB_PDFS=false - 2006+ have a spreadsheet for every
 *   table, so you lose only the narrative chapters and the PDF-only old years.
 *
 * NAMING + LOCATION:
 *       Downloads/<DOWNLOAD_SUBDIR>/<PUBLICATION_DIR>/<year>/<section>/<NNN>_<name>.<ext>
 *   e.g. Downloads/rbi/state-finances/2026/appendix-i-revenue-receipts/001_states-andhra-pradesh-arunachal-pradesh-assam-bihar.xlsx
 *        Downloads/rbi/state-finances/2026/statements/001_statement-1-major-fiscal-indicators.xlsx
 *        Downloads/rbi/state-finances/2026/chapters/002_ii-fiscal-position-of-the-state-governments.pdf
 *   - <year>    : edition, AUTO-DETECTED from the active archive tab.
 *   - <section> : the RBI section header the file sits under (chapters,
 *                 appendix-tables, statements, appendix-i-revenue-receipts, ...).
 *                 Keeps Appendix I (receipts) and Appendix II (expenditure)
 *                 apart even though their rows are the same state groups.
 *   - <NNN>     : the file's order within its section, zero-padded. A data
 *                 table and its PDF twin share the same NNN (one logical row).
 *   - <name>    : the RBI caption, slugified (the stable cross-year identity).
 *   GM_download creates the nested folders under Downloads. If your setup
 *   flattens subfolders, the section is NOT in the filename, so prefer the
 *   GM_download "Browser API" mode (whitelist 'xls,xlsx,pdf') to preserve it.
 *   Move Downloads/<DOWNLOAD_SUBDIR>/ into the repo .runtime/ when done.
 *
 * VOLUME WARNING:
 *   This publication is large. A full all-editions sweep with PDFs on is
 *   several thousand files; at the default 5s spacing that is a multi-hour
 *   run. Options: run one edition at a time, lower the delay, or set
 *   GRAB_PDFS=false for a spreadsheets-only pass.
 *
 * CONTROLS (Tampermonkey menu + on-page bar):
 *   - Open RBI State Finances site
 *   - Download this edition / Download ALL editions
 *   - Set edition/year override (blank = auto-detect)
 *   - Set delay seconds (pause between downloads)
 */

(function () {
  "use strict";

  // Running script version, surfaced in the UI + logs so you can confirm the
  // active code matches the file. Tampermonkey caches by @version, so it MUST
  // be bumped on every change. Sourced from GM_info so it never drifts.
  const VERSION =
    (typeof GM_info !== "undefined" &&
      GM_info.script &&
      GM_info.script.version) ||
    "1.0.0";

  // ======================================================================
  // CONFIG - edit here. Everything below is mechanism.
  // ======================================================================
  const CONFIG = {
    SITE_URL:
      "https://www.rbi.org.in/Scripts/AnnualPublications.aspx" +
      "?head=State+Finances+%3a+A+Study+of+Budgets",

    // Saved under the browser Downloads folder as
    // <DOWNLOAD_SUBDIR>/<PUBLICATION_DIR>/<year>/<section>/ ; mirror it into
    // the repo's .runtime/ when done.
    DOWNLOAD_SUBDIR: "rbi",
    PUBLICATION_DIR: "state-finances",

    // What to capture. Both ON = "collect all the data" (the default). For a
    // fast, data-only pass set GRAB_PDFS=false (keeps .xlsx + .xls only).
    GRAB_SPREADSHEETS: true, // .xlsx + .xls - the machine-readable tables
    GRAB_PDFS: true, // .pdf - narrative chapters + PDF twins + PDF-only years

    // Edition year. Auto-detected from the active archive tab; this is only
    // the fallback when detection fails (and the menu override default).
    DEFAULT_YEAR: "2026",
    AUTO_DETECT_YEAR: true,

    // Pause between downloads. Raise it if the F5 edge re-challenges mid-run;
    // lower it for a warm session. Configurable from the menu.
    DEFAULT_DELAY_SECONDS: 5,

    // Try Tampermonkey's GM_download (creates the nested folders); fall back
    // to a flat anchor save (filename keeps order + name, loses the section).
    USE_GM_DOWNLOAD: true,

    LOG_PREFIX: "[yen-gov RBI SF]",
  };

  // Persisted-setting keys + lifecycle event names (config-as-data).
  const KEYS = { YEAR: "year", DELAY_SECONDS: "delaySeconds" };
  const EVENTS = {
    INIT: "init",
    RUN_START: "run_start",
    SCRAPE: "scrape",
    DOWNLOAD_OK: "download_ok",
    DOWNLOAD_FAIL: "download_fail",
    WAIT: "wait",
    RUN_DONE: "run_done",
    SETTING: "setting",
  };

  // ======================================================================
  // mechanism
  // ======================================================================
  // A genuine payload is a ZIP container (.xlsx), an OLE2 / CFBF compound
  // document (legacy .xls), or a PDF ("%PDF"). The F5 CAPTCHA interstitial is
  // HTML ("<!DOCTYPE..."), so matching any of these magics is what
  // distinguishes a real download from a blocked one.
  const FILE_MAGICS = [
    [0x50, 0x4b, 0x03, 0x04], // "PK\x03\x04" - ZIP / OOXML .xlsx
    [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1], // OLE2 / CFBF legacy .xls
    [0x25, 0x50, 0x44, 0x46], // "%PDF" - .pdf
  ];
  const MIME = {
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    xls: "application/vnd.ms-excel",
    pdf: "application/pdf",
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Edition year: prefer the page's active archive tab (a.year.active), so we
  // never mislabel across editions. The override / DEFAULT_YEAR is only a
  // fallback when detection fails.
  function detectYear() {
    if (!CONFIG.AUTO_DETECT_YEAR) return null;
    const active = document.querySelector(
      "a.year.active, a.year.selected, .year.active"
    );
    const t = active && (active.innerText || active.textContent || "").trim();
    return t && /^(19|20)\d{2}$/.test(t) ? t : null;
  }

  const getYearOverride = () => GM_getValue(KEYS.YEAR, "");
  const getYear = () => detectYear() || getYearOverride() || CONFIG.DEFAULT_YEAR;
  const getDelayMs = () =>
    GM_getValue(KEYS.DELAY_SECONDS, CONFIG.DEFAULT_DELAY_SECONDS) * 1000;

  function log(event, message) {
    const line = `${event}: ${message}`;
    // eslint-disable-next-line no-console
    console.log(CONFIG.LOG_PREFIX, line); // full history -> browser console
    if (panelLog) panelLog.textContent = line; // strip shows the latest line
  }

  function isPayload(buf) {
    if (!buf || buf.byteLength < 8) return false;
    const head = new Uint8Array(buf.slice(0, 8));
    return FILE_MAGICS.some((sig) => sig.every((b, i) => head[i] === b));
  }

  // Real download extension, lower-cased from the RBI URL.
  function extFor(url) {
    const m = url.match(/\.([A-Za-z]{2,4})(\?|$)/);
    return m ? m[1].toLowerCase() : "";
  }

  // The set of extensions we want this run, from CONFIG.
  function wantedExts() {
    const exts = [];
    if (CONFIG.GRAB_SPREADSHEETS) exts.push("xlsx", "xls");
    if (CONFIG.GRAB_PDFS) exts.push("pdf");
    return new Set(exts);
  }

  // Slugify an RBI caption into a stable, filesystem-safe identity segment.
  function slugify(s) {
    return (s || "")
      .toLowerCase()
      .replace(/&/g, " and ")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80)
      .replace(/-+$/g, "");
  }

  // Strip RBI's trailing file-size text ("16 kb 122 kb") and collapse space.
  function cleanName(rowText) {
    return (rowText || "")
      .replace(/\s+/g, " ")
      .replace(/\s+[\d.]+\s*kb.*$/i, "")
      .trim();
  }

  // Turn a section header (h2.dop_header) into a stable folder slug. Handles
  // the date header (front-matter), the Appendix I-IV headers (which carry a
  // long ".. of States and Union Territories with Legislature" tail and an
  // "Appendices I to IV:" preamble), and drops fiscal-year tags like "2025-26".
  function sectionSlug(headerText) {
    const raw = (headerText || "").replace(/\s+/g, " ").trim();
    // a "Jan 23, 2026"-style date header sits above the foreword/contents
    if (/^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}$/.test(raw)) return "front-matter";
    let t = raw.replace(/\b\d{4}-\d{2}\b/g, " "); // drop fiscal-year tags
    // prefer the LAST "Appendix <roman>: <name>" when the header bundles the
    // section preamble with the first appendix
    const apps = [
      ...t.matchAll(/Appendix\s+([IVXLC]+)\s*:?\s*([A-Za-z][^:]*)/gi),
    ];
    if (apps.length) {
      const a = apps[apps.length - 1];
      t = `Appendix ${a[1]} ${a[2]}`;
    }
    let s = slugify(t)
      .replace(/-of-states-and-union-territories-with-legislature.*$/, "")
      .replace(/^appendices-i-to-iv-/, "");
    return (s.slice(0, 60).replace(/-+$/, "") || "misc");
  }

  // Read the loaded edition page in document order; bucket each wanted file
  // under its section header. A data table and its PDF twin share one section
  // index (keyed on the row caption), so they sort together. Returns
  // [{section, idx, name, url, ext}], de-duplicated by URL.
  function scrapeAll() {
    const wanted = wantedExts();
    const nodes = Array.from(
      document.querySelectorAll(
        'h2.dop_header, a[href*="rbidocs.rbi.org.in/rdocs/"]'
      )
    );
    let section = "front-matter";
    const counters = {}; // section -> next index
    const rowIdx = {}; // section -> { caption -> index } (twins share an index)
    const indexFor = (sec, caption) => {
      counters[sec] = counters[sec] || 0;
      rowIdx[sec] = rowIdx[sec] || {};
      if (rowIdx[sec][caption] == null) rowIdx[sec][caption] = ++counters[sec];
      return rowIdx[sec][caption];
    };
    const seen = new Set();
    const items = [];
    for (const n of nodes) {
      if (n.tagName === "H2") {
        section = sectionSlug(n.innerText);
        continue;
      }
      const url = n.href;
      const ext = extFor(url);
      if (!wanted.has(ext)) continue;
      if (seen.has(url)) continue;
      seen.add(url);
      const row = n.closest("tr") || n.parentElement;
      const name = cleanName(row && row.innerText) || "item";
      const idx = indexFor(section, name);
      items.push({ section, idx, name, url, ext });
    }
    return items;
  }

  function fetchValidate(url) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "GET",
        url,
        responseType: "arraybuffer",
        headers: { Referer: CONFIG.SITE_URL },
        timeout: 120_000,
        onload: (res) => {
          if (res.status !== 200) return reject(new Error(`HTTP ${res.status}`));
          if (!isPayload(res.response))
            return reject(
              new Error(
                "not a workbook/PDF (F5 CAPTCHA/HTML) - open rbidocs.rbi.org.in " +
                  "once, clear the check, then retry"
              )
            );
          resolve(res.response);
        },
        onerror: () => reject(new Error("network/edge error (connection closed)")),
        ontimeout: () => reject(new Error("timeout")),
      });
    });
  }

  function anchorSave(objectUrl, filename) {
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // Save validated bytes. Prefer GM_download (keeps the nested folders); fall
  // back to a flat anchor save (filename keeps order + name, loses section).
  function saveFile(buf, subpath, filename, ext) {
    const objectUrl = URL.createObjectURL(
      new Blob([buf], { type: MIME[ext] || "application/octet-stream" })
    );
    const revoke = () => setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
    if (CONFIG.USE_GM_DOWNLOAD && typeof GM_download === "function") {
      return new Promise((resolve) => {
        let done = false;
        const fallback = (why) => {
          if (done) return;
          done = true;
          if (String(why).includes("not_whitelisted") && !whitelistHintShown) {
            whitelistHintShown = true;
            log(
              EVENTS.SETTING,
              "for nested folders enable GM_download: Tampermonkey > " +
                "Settings > Downloads -> Mode 'Browser API' + whitelist " +
                "'xls,xlsx,pdf' (saving flat for now)"
            );
          }
          anchorSave(objectUrl, filename);
          revoke();
          resolve("anchor");
        };
        try {
          GM_download({
            url: objectUrl,
            name: subpath,
            saveAs: false,
            onload: () => {
              if (done) return;
              done = true;
              revoke();
              resolve("gm_download");
            },
            onerror: (e) => fallback((e && (e.error || e.details)) || "error"),
            ontimeout: () => fallback("timeout"),
          });
        } catch (e) {
          fallback(e && e.message ? e.message : "throw");
        }
      });
    }
    anchorSave(objectUrl, filename);
    revoke();
    return Promise.resolve("anchor");
  }

  let running = false;
  let whitelistHintShown = false;

  // Download every wanted file on the CURRENTLY loaded edition page. Pure
  // worker - no run-guard, no year switching - so both the single-edition
  // button and the all-editions sweep reuse it. Returns {ok, total}.
  async function downloadEditionOnce() {
    const year = getYear();
    const delayMs = getDelayMs();
    const source = detectYear() ? "auto-detected" : "override/default";
    const grab =
      (CONFIG.GRAB_SPREADSHEETS ? "xls/xlsx" : "") +
      (CONFIG.GRAB_SPREADSHEETS && CONFIG.GRAB_PDFS ? "+" : "") +
      (CONFIG.GRAB_PDFS ? "pdf" : "");
    log(
      EVENTS.RUN_START,
      `edition ${year} (${source}), grab ${grab || "nothing"}, delay ${
        delayMs / 1000
      }s`
    );
    const items = scrapeAll();
    log(EVENTS.SCRAPE, `${items.length} file(s) on this edition`);
    let ok = 0;
    for (let i = 0; i < items.length; i++) {
      const { section, idx, name, url, ext } = items[i];
      const nnn = String(idx).padStart(3, "0");
      const filename = `${nnn}_${slugify(name)}.${ext}`;
      const subpath =
        `${CONFIG.DOWNLOAD_SUBDIR}/${CONFIG.PUBLICATION_DIR}/${year}/` +
        `${section}/${filename}`;
      log(
        EVENTS.SCRAPE,
        `(${i + 1}/${items.length}) ${section}/${nnn} ${name}`
      );
      try {
        const buf = await fetchValidate(url);
        const via = await saveFile(buf, subpath, filename, ext);
        ok++;
        log(
          EVENTS.DOWNLOAD_OK,
          `${buf.byteLength.toLocaleString()} bytes -> ${subpath} (${via})`
        );
      } catch (e) {
        log(EVENTS.DOWNLOAD_FAIL, `${section}/${nnn} ${name}: ${e.message}`);
      }
      if (i < items.length - 1) {
        log(EVENTS.WAIT, `${delayMs / 1000}s before next`);
        await sleep(delayMs);
      }
    }
    log(
      EVENTS.RUN_DONE,
      `${ok}/${items.length} saved to Downloads/${CONFIG.DOWNLOAD_SUBDIR}/` +
        `${CONFIG.PUBLICATION_DIR}/${year}/ - move that into the repo .runtime/`
    );
    return { ok, total: items.length };
  }

  async function startRun() {
    if (running) {
      log(EVENTS.RUN_START, "already running; ignoring");
      return;
    }
    running = true;
    try {
      await downloadEditionOnce();
    } finally {
      running = false;
    }
  }

  // Year tabs are <a class="year">2016</a> wired to the site's own
  // GetYear(...) AJAX. Return the four-digit ones in page order.
  function yearTabs() {
    return Array.from(document.querySelectorAll("a.year"))
      .map((a) => ({ el: a, year: (a.innerText || "").trim() }))
      .filter((t) => /^(19|20)\d{2}$/.test(t.year));
  }

  // Switch the page to one archive edition (clicks the tab, firing the site's
  // GetYear AJAX) and wait until that edition has fully rendered: the active
  // tab must read <year> AND the doc-link count must hold steady across two
  // polls (the listing is one innerHTML swap, so a stable count = done).
  async function switchToYear(tab) {
    tab.el.click();
    const deadline = Date.now() + 30_000;
    let last = -1;
    let stable = 0;
    while (Date.now() < deadline) {
      await sleep(700);
      const active = detectYear();
      const count = document.querySelectorAll(
        'a[href*="rbidocs.rbi.org.in/rdocs/"]'
      ).length;
      if (active === tab.year && count > 0) {
        if (count === last) {
          if (++stable >= 2) return true;
        } else {
          stable = 0;
          last = count;
        }
      }
    }
    return false;
  }

  // Sweep EVERY archive edition: switch to each year tab and download all of
  // its files. One click captures the whole publication (this is a long run -
  // see the VOLUME WARNING in the header).
  async function downloadAllYears() {
    if (running) {
      log(EVENTS.RUN_START, "already running; ignoring");
      return;
    }
    running = true;
    try {
      const tabs = yearTabs();
      log(
        EVENTS.RUN_START,
        `ALL editions: ${tabs.map((t) => t.year).join(", ")}`
      );
      let grand = 0;
      for (const tab of tabs) {
        log(EVENTS.RUN_START, `switching to edition ${tab.year} ...`);
        const ready = await switchToYear(tab);
        if (!ready) {
          log(
            EVENTS.DOWNLOAD_FAIL,
            `edition ${tab.year}: did not load in time; skipped`
          );
          continue;
        }
        const { ok } = await downloadEditionOnce();
        grand += ok;
      }
      log(EVENTS.RUN_DONE, `ALL editions complete - ${grand} file(s) saved`);
    } finally {
      running = false;
    }
  }

  function setYear() {
    const v = prompt(
      "Edition/year OVERRIDE (single year e.g. 2026; blank = auto-detect):",
      getYearOverride()
    );
    if (v === null) return;
    GM_setValue(KEYS.YEAR, v.trim());
    log(
      EVENTS.SETTING,
      v.trim()
        ? `year override = ${v.trim()} (menu updates on reload)`
        : "year override cleared - using auto-detect"
    );
  }

  function setDelay() {
    const v = prompt(
      "Delay between downloads (seconds):",
      String(getDelayMs() / 1000)
    );
    const n = parseInt(v, 10);
    if (!Number.isNaN(n) && n >= 0) {
      GM_setValue(KEYS.DELAY_SECONDS, n);
      log(EVENTS.SETTING, `delay = ${n}s (menu label updates on reload)`);
    }
  }

  // ======================================================================
  // UI: Tampermonkey menu + a minimal on-page log panel
  // ======================================================================
  let panelLog = null;
  function buildPanel() {
    const bar = document.createElement("div");
    bar.style.cssText =
      "position:fixed;left:0;right:0;bottom:0;z-index:2147483647;background:#0b1f3a;" +
      "color:#fff;font:12px/1.4 system-ui,sans-serif;padding:6px 10px;display:flex;" +
      "align-items:center;gap:10px;box-shadow:0 -2px 12px rgba(0,0,0,.4);";
    const title = document.createElement("span");
    title.textContent = `yen-gov RBI State Finances ${getYear()} v${VERSION}`;
    title.style.cssText = "flex:0 0 auto;font-weight:600;";
    const btn = document.createElement("button");
    btn.textContent = "This edition";
    btn.style.cssText =
      "flex:0 0 auto;background:#2a6df4;color:#fff;border:0;border-radius:6px;" +
      "padding:5px 12px;cursor:pointer;font:12px system-ui,sans-serif;";
    btn.addEventListener("click", startRun);
    const allBtn = document.createElement("button");
    allBtn.textContent = "ALL editions";
    allBtn.style.cssText =
      "flex:0 0 auto;background:#1f8b4c;color:#fff;border:0;border-radius:6px;" +
      "padding:5px 12px;cursor:pointer;font:12px system-ui,sans-serif;";
    allBtn.addEventListener("click", downloadAllYears);
    panelLog = document.createElement("span");
    panelLog.style.cssText =
      "flex:1 1 auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" +
      "opacity:.92;font:11px/1.4 ui-monospace,Consolas,monospace;";
    const hide = document.createElement("button");
    hide.textContent = "hide";
    hide.style.cssText =
      "flex:0 0 auto;background:transparent;color:#cdd9ee;border:1px solid #2a6df4;" +
      "border-radius:4px;padding:3px 9px;cursor:pointer;font:11px system-ui,sans-serif;";
    hide.addEventListener("click", () => bar.remove());
    bar.append(title, btn, allBtn, panelLog, hide);
    document.body.appendChild(bar);
  }

  function registerMenu() {
    GM_registerMenuCommand("Open RBI State Finances site", () =>
      GM_openInTab(CONFIG.SITE_URL, { active: true })
    );
    GM_registerMenuCommand("Download this edition", startRun);
    GM_registerMenuCommand("Download ALL editions (every year)", downloadAllYears);
    GM_registerMenuCommand(
      `Set edition/year override (now: ${getYearOverride() || "auto=" + getYear()})`,
      setYear
    );
    GM_registerMenuCommand(
      `Set delay seconds (now: ${getDelayMs() / 1000})`,
      setDelay
    );
  }

  // Only activate on the State Finances publication page. The @match is the
  // whole rbi.org.in site so the script survives in-site navigations, but the
  // panel + menu only mount here; the sibling Handbook script guards itself
  // the same way, so the two never both paint a panel on one page.
  function isStateFinancesPage() {
    return /State Finances\s*:?\s*A Study of Budgets/i.test(
      document.title || ""
    );
  }

  if (isStateFinancesPage()) {
    buildPanel();
    registerMenu();
    log(
      EVENTS.INIT,
      `v${VERSION} ready - edition ${getYear()}${detectYear() ? " (auto)" : ""}, ` +
        `spreadsheets=${CONFIG.GRAB_SPREADSHEETS}, pdfs=${CONFIG.GRAB_PDFS}, ` +
        `delay ${getDelayMs() / 1000}s`
    );
  }
})();
