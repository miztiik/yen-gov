// ==UserScript==
// @name         yen-gov - RBI Handbook (Indian States) bulk stager
// @namespace    yen-gov
// @version      3.2.0
// @description  Config-driven BULK downloader for the RBI Handbook of Statistics on Indian States. Grabs EVERY table on the loaded edition page (fiscal, industry, agriculture, prices, environment, state domestic product, health, socio-demographic - ~182 in 2025, ~125 in 2016), modern .xlsx AND legacy .xls alike (the 2016 edition and the 2017 INDUSTRY section are served as .xls - v3.1 silently skipped all 148 of them). Runs inside your own trusted RBI browser session (the F5 anti-bot CAPTCHA is already satisfied - nothing is bypassed). Reads each table's XLS/XLSX link + RBI caption + table number LIVE from the page, auto-detects the single-year edition, validates each file is a real workbook (ZIP or OLE2 magic), and saves it as <year>_t<NNN>_<rbi-name>.<xls|xlsx> under a year folder. 'Download ALL editions' sweeps every archive year in one click. Controls in the Tampermonkey menu.
// @author       yen-gov
// @updateURL    https://raw.githubusercontent.com/miztiik/yen-gov/main/tools/rbi_handbook_download.user.js
// @downloadURL  https://raw.githubusercontent.com/miztiik/yen-gov/main/tools/rbi_handbook_download.user.js
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
 * WHY a userscript (and why this is NOT a CAPTCHA / WAF bypass):
 *   The RBI document host (rbidocs.rbi.org.in) sits behind an F5 BIG-IP
 *   anti-bot layer that serves a CAPTCHA to scripted clients. A person
 *   browsing rbi.org.in clears that check naturally. This script runs INSIDE
 *   that already-trusted browser session and only automates the clicks a
 *   human would otherwise do by hand - it does not solve, forge, or skip the
 *   CAPTCHA.
 *
 * WHAT it grabs:
 *   EVERY table on the loaded edition page (not a curated subset) - you keep
 *   the lot and decide locally what to ingest. Each file is named from the
 *   RBI caption, NOT an assumed mapping, because table NUMBERS drift across
 *   editions (2016 has ~125 tables, 2025 has ~182). The RBI table NAME is the
 *   stable identity; the table number is recorded too, but only as a
 *   within-edition correlator.
 *
 * NAMING + LOCATION:
 *       Downloads/<DOWNLOAD_SUBDIR>/<HANDBOOK_DIR>/<year>/<year>_t<NNN>_<rbi-name>.xlsx
 *   e.g. Downloads/rbi/handbook-states/2025/2025_t002_state-wise-birth-rate.xlsx
 *   - <year>    : single-year edition, AUTO-DETECTED from the page's active
 *                 archive tab (2016..2025); override via the menu if needed.
 *   - t<NNN>    : RBI table number on THIS edition, zero-padded (sortable).
 *   - <rbi-name>: the RBI caption, slugified (the stable cross-year identity).
 *   GM_download creates the <year> subfolder under Downloads (default
 *   Tampermonkey download mode). If your setup flattens subfolders, the files
 *   still carry year + table number + name, so nothing is ambiguous. Move the
 *   Downloads/<DOWNLOAD_SUBDIR>/ subtree into the repo's .runtime/ when done.
 *
 * CONTROLS (Tampermonkey menu, top-right extension icon):
 *   - Open RBI Handbook site
 *   - Download ALL tables (this edition)
 *   - Set edition/year override (blank = auto-detect)
 *   - Set delay seconds (pause between downloads)
 */

(function () {
  "use strict";

  // Running script version, surfaced in the UI + logs so you can confirm the
  // active code matches the file. Tampermonkey caches by @version, so it MUST
  // be bumped on every change (else an update silently keeps the old code).
  // Sourced from GM_info so it never drifts from the metadata header.
  const VERSION =
    (typeof GM_info !== "undefined" &&
      GM_info.script &&
      GM_info.script.version) ||
    "3.2.0";

  // ======================================================================
  // CONFIG - edit here. Everything below is mechanism.
  // ======================================================================
  const CONFIG = {
    SITE_URL:
      "https://www.rbi.org.in/Scripts/AnnualPublications.aspx" +
      "?head=Handbook+of+Statistics+on+Indian+States",

    // Saved under the browser Downloads folder as
    // <DOWNLOAD_SUBDIR>/<HANDBOOK_DIR>/<year>/ ; mirror it into the repo's
    // .runtime/ when done.
    DOWNLOAD_SUBDIR: "rbi",
    HANDBOOK_DIR: "handbook-states", // distinguishes this from other RBI handbooks

    // Edition year. Auto-detected from the page's active archive tab; this is
    // only the fallback when detection fails (and the menu override default).
    DEFAULT_YEAR: "2025",
    AUTO_DETECT_YEAR: true,

    // Pause between downloads. The page has ~182 tables, so 5s ~= 15 min for a
    // full edition. Raise it if the F5 edge re-challenges mid-run; lower it if
    // the session stays warm. Configurable from the menu.
    DEFAULT_DELAY_SECONDS: 5,

    // Grab every table (default). To restrict, set GRAB_ALL=false and list the
    // RBI table numbers you want for the CURRENT edition (numbers are
    // edition-specific). Example: [2, 3, 4, 6, 7].
    GRAB_ALL: true,
    ONLY_TABLE_NUMBERS: [],

    // Try Tampermonkey's GM_download (creates the <year> subfolder); fall back
    // to a flat anchor save (filename still fully prefixed) if unavailable.
    USE_GM_DOWNLOAD: true,

    LOG_PREFIX: "[yen-gov RBI HBS]",
  };

  // Persisted-setting keys + lifecycle event names (config-as-data).
  const KEYS = { YEAR: "year", DELAY_SECONDS: "delaySeconds" };
  const EVENTS = {
    INIT: "init",
    RUN_START: "run_start",
    SCRAPE: "scrape",
    DOWNLOAD_OK: "download_ok",
    DOWNLOAD_FAIL: "download_fail",
    NOT_FOUND: "not_found",
    WAIT: "wait",
    RUN_DONE: "run_done",
    SETTING: "setting",
  };

  // ======================================================================
  // mechanism
  // ======================================================================
  // A genuine workbook is either a ZIP container (modern .xlsx) or an OLE2 /
  // CFBF compound document (legacy .xls). RBI serves the 2016 edition - and
  // the 2017 INDUSTRY section - as legacy .xls; everything 2018+ is .xlsx.
  // The F5 CAPTCHA interstitial is HTML ("<!DOCTYPE..."), so matching either
  // binary magic is what distinguishes a real download from a blocked one.
  const FILE_MAGICS = [
    [0x50, 0x4b, 0x03, 0x04], // "PK\x03\x04" - ZIP / OOXML .xlsx
    [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1], // OLE2 / CFBF legacy .xls
  ];
  const MIME_XLSX =
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const MIME_XLS = "application/vnd.ms-excel";
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // Edition year: prefer the page's active archive tab (a.year.active = the
  // single year like "2025"), so we never mislabel across editions. The menu
  // override / DEFAULT_YEAR is only a fallback when detection fails.
  function detectYear() {
    if (!CONFIG.AUTO_DETECT_YEAR) return null;
    const active = document.querySelector(
      "a.year.active, a.year.selected, .year.active"
    );
    const t = active && (active.innerText || active.textContent || "").trim();
    return t && /^20\d{2}$/.test(t) ? t : null;
  }

  const getYearOverride = () => GM_getValue(KEYS.YEAR, "");
  const getYear = () => detectYear() || getYearOverride() || CONFIG.DEFAULT_YEAR;
  const getDelayMs = () =>
    GM_getValue(KEYS.DELAY_SECONDS, CONFIG.DEFAULT_DELAY_SECONDS) * 1000;

  function log(event, message) {
    const line = `${event}: ${message}`;
    // eslint-disable-next-line no-console
    console.log(CONFIG.LOG_PREFIX, line); // full history -> browser console
    if (panelLog) panelLog.textContent = line; // strip shows the latest line only
  }

  function isWorkbook(buf) {
    if (!buf || buf.byteLength < 8) return false;
    const head = new Uint8Array(buf.slice(0, 8));
    return FILE_MAGICS.some((sig) => sig.every((b, i) => head[i] === b));
  }

  // Real download extension, preserved from the RBI URL so legacy .xls files
  // are named honestly (and parsed by the right reader downstream).
  function extFor(url) {
    return /\.XLSX(\?|$)/i.test(url) ? "xlsx" : "xls";
  }
  function mimeFor(ext) {
    return ext === "xls" ? MIME_XLS : MIME_XLSX;
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

  // Parse "Table N: <Name> <size> kb" from a link's row -> {num, name}.
  // Tolerant of RBI's inconsistencies: missing space ("Table165"), missing
  // colon, and trailing file-size text. Falls back for non-table XLSX links.
  function parseRow(rowText) {
    const txt = (rowText || "").replace(/\s+/g, " ").trim();
    let m = txt.match(/Table\s*(\d+)\s*:?\s*(.+?)\s+[\d.]+\s*kb/i);
    if (!m) m = txt.match(/Table\s*(\d+)\s*:?\s*(.+)/i);
    if (m) {
      // strip any trailing "16 kb 135 kb" the greedy fallback may have grabbed
      const name = m[2].replace(/\s+[\d.]+\s*kb.*$/i, "").trim();
      return { num: m[1], name };
    }
    return { num: null, name: txt.slice(0, 60) };
  }

  // Read the loaded edition page; return every workbook table as
  // {num, name, url}, de-duplicated, optionally filtered by table number.
  // Matches BOTH .xls and .xlsx - RBI mixes them across editions/sections,
  // and the .XLSX?-only filter in v3.1 silently dropped every legacy .xls.
  function scrapeAll() {
    const anchors = Array.from(document.querySelectorAll("a")).filter((a) =>
      /\.XLSX?(\?|$)/i.test(a.href)
    );
    const seen = new Set();
    const tables = [];
    for (const a of anchors) {
      if (seen.has(a.href)) continue;
      seen.add(a.href);
      const row = a.closest("tr") || a.parentElement;
      const { num, name } = parseRow((row && row.innerText) || "");
      if (
        !CONFIG.GRAB_ALL &&
        CONFIG.ONLY_TABLE_NUMBERS.length &&
        !(num && CONFIG.ONLY_TABLE_NUMBERS.includes(Number(num)))
      ) {
        continue;
      }
      tables.push({ num, name, url: a.href });
    }
    return tables;
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
          if (!isWorkbook(res.response))
            return reject(
              new Error(
                "not a workbook (F5 CAPTCHA/HTML) - open rbidocs.rbi.org.in " +
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

  // Save validated bytes. Prefer GM_download (keeps the year subfolder);
  // fall back to a flat anchor save (filename still fully prefixed).
  function saveFile(buf, subpath, filename, mime) {
    const objectUrl = URL.createObjectURL(
      new Blob([buf], { type: mime || MIME_XLSX })
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
              "for <year> subfolders enable GM_download: Tampermonkey > " +
                "Settings > Downloads -> Mode 'Browser API' + whitelist " +
                "'xls,xlsx' (saving flat for now)"
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

  // Download every table on the CURRENTLY loaded edition page. Pure worker -
  // no run-guard, no year switching - so both the single-edition button and
  // the all-editions sweep reuse it. Returns {ok, total}.
  async function downloadEditionOnce() {
    const year = getYear();
    const delayMs = getDelayMs();
    const source = detectYear() ? "auto-detected" : "override/default";
    log(EVENTS.RUN_START, `edition ${year} (${source}), delay ${delayMs / 1000}s`);
    const tables = scrapeAll();
    log(
      EVENTS.SCRAPE,
      `${tables.length} table(s) on this edition` +
        (CONFIG.GRAB_ALL ? " (grab-all)" : " (filtered)")
    );
    let ok = 0;
    for (let i = 0; i < tables.length; i++) {
      const { num, name, url } = tables[i];
      const tnum = num ? "t" + String(num).padStart(3, "0") : "t000";
      const ext = extFor(url);
      const filename = `${year}_${tnum}_${slugify(name)}.${ext}`;
      const subpath =
        `${CONFIG.DOWNLOAD_SUBDIR}/${CONFIG.HANDBOOK_DIR}/${year}/${filename}`;
      log(EVENTS.SCRAPE, `(${i + 1}/${tables.length}) ${tnum} ${name}`);
      try {
        const buf = await fetchValidate(url);
        const via = await saveFile(buf, subpath, filename, mimeFor(ext));
        ok++;
        log(
          EVENTS.DOWNLOAD_OK,
          `${buf.byteLength.toLocaleString()} bytes -> ${subpath} (${via})`
        );
      } catch (e) {
        log(EVENTS.DOWNLOAD_FAIL, `${tnum} ${name}: ${e.message}`);
      }
      if (i < tables.length - 1) {
        log(EVENTS.WAIT, `${delayMs / 1000}s before next`);
        await sleep(delayMs);
      }
    }
    log(
      EVENTS.RUN_DONE,
      `${ok}/${tables.length} saved to Downloads/${CONFIG.DOWNLOAD_SUBDIR}/` +
        `${CONFIG.HANDBOOK_DIR}/${year}/ - move that into the repo .runtime/`
    );
    return { ok, total: tables.length };
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

  // Year tabs are <a class="year">2017</a> wired to the site's own
  // GetYear(...) AJAX. Return the four-digit ones in page order.
  function yearTabs() {
    return Array.from(document.querySelectorAll("a.year"))
      .map((a) => ({ el: a, year: (a.innerText || "").trim() }))
      .filter((t) => /^20\d{2}$/.test(t.year));
  }

  // Switch the page to one archive edition (clicks the tab, firing the site's
  // GetYear AJAX) and wait until that edition has fully rendered: the active
  // tab must read <year> AND the workbook-link count must hold steady across
  // two polls (the listing is one innerHTML swap, so a stable count = done).
  async function switchToYear(tab) {
    tab.el.click();
    const deadline = Date.now() + 25_000;
    let last = -1;
    let stable = 0;
    while (Date.now() < deadline) {
      await sleep(600);
      const active = detectYear();
      const count = document.querySelectorAll(
        'a[href*="/rdocs/Publications/DOCs/"]'
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
  // its tables. One click captures the whole publication, oldest .xls years
  // included.
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
      "Edition/year OVERRIDE (single year e.g. 2025; blank = auto-detect):",
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
    title.textContent = `yen-gov RBI HBS ${getYear()} v${VERSION}`;
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
    GM_registerMenuCommand("Open RBI Handbook site", () =>
      GM_openInTab(CONFIG.SITE_URL, { active: true })
    );
    GM_registerMenuCommand("Download ALL tables (this edition)", startRun);
    GM_registerMenuCommand(
      "Download ALL editions (every year)",
      downloadAllYears
    );
    GM_registerMenuCommand(
      `Set edition/year override (now: ${getYearOverride() || "auto=" + getYear()})`,
      setYear
    );
    GM_registerMenuCommand(
      `Set delay seconds (now: ${getDelayMs() / 1000})`,
      setDelay
    );
  }

  // Only activate on the Handbook publication page. The @match is the whole
  // rbi.org.in site so the script survives in-site navigations, but the panel
  // + menu only mount here; the sibling State Finances script guards itself
  // the same way, so the two never both paint a panel on one page.
  function isHandbookPage() {
    return /Handbook of Statistics on Indian States/i.test(
      document.title || ""
    );
  }

  if (isHandbookPage()) {
    buildPanel();
    registerMenu();
    log(
      EVENTS.INIT,
      `v${VERSION} ready - edition ${getYear()}${detectYear() ? " (auto)" : ""}, ` +
        `delay ${getDelayMs() / 1000}s, grab-all=${CONFIG.GRAB_ALL}`
    );
  }
})();
