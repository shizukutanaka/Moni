"use strict";
/*
 * Moni viewer UI test — drives index.html in Electron (headless via Xvfb).
 * Verifies: no page errors, sample renders all 10 category cards, null items
 * are shown honestly ("取得不可"), battery=null shows "なし", search filters,
 * language switch re-renders in English, text export is generated.
 *
 * Run: MONI_ELECTRON=/path/to/electron xvfb-run -a <electron> tests/ui-test/main.js
 * The electron binary path comes from the ELECTRON env var via the runner,
 * or falls back to "electron" on PATH. This script is the app main.
 */
const { app, BrowserWindow } = require("electron");
const path = require("path");
const fs = require("fs");

app.setPath("userData", path.join(__dirname, ".userdata"));
app.disableHardwareAcceleration();

const PAGE = "file://" + path.join(__dirname, "..", "..", "index.html");
const results = [];
const pageErrors = [];
function check(name, cond, detail) {
  results.push({ name, pass: !!cond });
  console.log((cond ? "PASS" : "FAIL") + " | " + name + (detail ? " | " + detail : ""));
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let wc;
async function js(code) { return wc.executeJavaScript(code, true); }

app.whenReady().then(async () => {
  let exitCode = 0;
  try {
    const win = new BrowserWindow({ width: 1200, height: 900, show: false, webPreferences: { contextIsolation: true } });
    wc = win.webContents;
    wc.on("console-message", (e, level, message) => { if (level >= 3) pageErrors.push(message); });
    wc.on("did-fail-load", (e, code, desc) => pageErrors.push("did-fail-load " + code + " " + desc));

    await wc.loadURL(PAGE);
    await sleep(600);

    check("T1 Moni hooks exposed", await js(`!!(window.Moni && window.Moni.loadSample)`));
    let init = await js(`({
      emptyShown: document.getElementById('emptyState').style.display !== 'none',
      cards: document.querySelectorAll('#cards .card').length
    })`);
    check("T2 initial empty state, no cards", init.emptyShown === true && init.cards === 0, JSON.stringify(init));

    /* Sample report: all categories rendered */
    await js(`window.Moni.setLang('ja'); window.Moni.loadSample(); 'ok'`);
    await sleep(300);
    let s = await js(`({
      cards: document.querySelectorAll('#cards .card').length,
      titles: Array.from(document.querySelectorAll('#cards .card h3')).map(h => h.textContent),
      bodyText: document.getElementById('cards').textContent,
      sampleBanner: document.getElementById('sampleBanner').style.display !== 'none',
      exportEnabled: !document.getElementById('btnExportTxt').disabled
    })`);
    check("T3 sample renders 10 category cards", s.cards === 10, "cards=" + s.cards);
    const wantTitles = ["システム概要", "CPU", "メモリ", "GPU", "マザーボード", "ストレージ", "ネットワーク", "ディスプレイ", "バッテリー", "USB / 周辺デバイス"];
    check("T4 all category titles present (ja)", wantTitles.every((x) => s.titles.some((y) => y.includes(x))), s.titles.join(" / "));
    check("T5 sample banner shown for sample data", s.sampleBanner === true);
    check("T6 export buttons enabled", s.exportEnabled === true);
    check("T7 sample values rendered", s.bodyText.includes("SAMPLE-DESKTOP") && s.bodyText.includes("DDR5") && s.bodyText.includes("2560 × 1440") && s.bodyText.includes("192.168.1.50"), "");
    check("T8 battery=null shows 'なし' wording", s.bodyText.includes("バッテリーは搭載されていません"), "");
    check("T9 null VRAM shown as 取得不可", s.bodyText.includes("取得不可"), "");
    check("T10 logical drive usage bar rendered", await js(`document.querySelectorAll('#cards .bar > div').length`) >= 1);

    /* Text export */
    const txt = await js(`window.Moni.buildTextExport()`);
    check("T11 text export contains sections and values",
      typeof txt === "string" && txt.includes("[メモリ]") && txt.includes("DDR5") && txt.includes("SAMPLE-DESKTOP") && txt.includes("[バッテリー]"),
      (txt || "").slice(0, 80));

    /* Search filter */
    await js(`{ const i = document.getElementById('searchInput'); i.value = 'DDR5'; i.dispatchEvent(new Event('input')); 'ok' }`);
    await sleep(200);
    let f = await js(`({
      visibleCards: Array.from(document.querySelectorAll('#cards .card')).filter(c => c.style.display !== 'none').length,
      memVisible: Array.from(document.querySelectorAll('#cards .card')).some(c => c.style.display !== 'none' && c.textContent.includes('メモリ'))
    })`);
    check("T12 search 'DDR5' leaves only matching card(s)", f.visibleCards === 1 && f.memVisible === true, JSON.stringify(f));
    await js(`{ const i = document.getElementById('searchInput'); i.value = ''; i.dispatchEvent(new Event('input')); 'ok' }`);
    await sleep(200);

    /* Custom report: battery present, empty arrays, sparse nulls */
    const custom = {
      format: "moni-report", version: 1, collectedAt: "2026-01-20T09:00:00+09:00",
      collector: "test", sampleData: false,
      system: { computerName: "TEST-PC", manufacturer: null, model: null, osName: "Windows 11", osVersion: null, osBuild: null, uptimeSeconds: 3600 },
      cpu: { name: "TestCPU", cores: 4, logicalProcessors: 8, maxClockMHz: 3000 },
      memory: { totalBytes: 17179869184, modules: [] },
      gpus: [],
      motherboard: { manufacturer: null, product: null, biosVersion: null, biosDate: null },
      storage: { physical: [], logical: [] },
      network: [],
      displays: [],
      battery: { chargePercent: 82, status: "Discharging", designCapacityMWh: 50000, fullChargeCapacityMWh: 46000 },
      peripherals: []
    };
    await js(`window.Moni.loadReport(${JSON.stringify(custom)}); 'ok'`);
    await sleep(300);
    let cu = await js(`({
      cards: document.querySelectorAll('#cards .card').length,
      bodyText: document.getElementById('cards').textContent,
      sampleBanner: document.getElementById('sampleBanner').style.display !== 'none'
    })`);
    check("T13 custom report renders 10 cards even with empty arrays", cu.cards === 10, "cards=" + cu.cards);
    check("T14 battery values shown (charge + health 92%)", cu.bodyText.includes("82 %") && cu.bodyText.includes("92 %"), "");
    check("T15 sample banner hidden for real report", cu.sampleBanner === false);
    check("T16 sparse nulls shown as 取得不可", cu.bodyText.includes("取得不可"), "");

    /* Language switch */
    await js(`window.Moni.setLang('en'); 'ok'`);
    await sleep(200);
    let en = await js(`({
      titles: Array.from(document.querySelectorAll('#cards .card h3')).map(h => h.textContent),
      na: document.getElementById('cards').textContent.includes('Unavailable'),
      none: document.getElementById('cards').textContent
    })`);
    check("T17 English titles after language switch",
      ["System", "Memory", "Battery", "USB / Peripherals"].every((x) => en.titles.some((y) => y.includes(x))), en.titles.join(" / "));
    check("T18 English 'Unavailable' for null items", en.na === true);

    /* Paste path + JSON parse error handling */
    let pe = await js(`window.Moni.parseAndLoad('{not json')`);
    check("T19 invalid JSON rejected without crashing", pe === false);
    let pb = await js(`window.Moni.parseAndLoad('\\uFEFF{"format":"moni-report","version":1}')`);
    check("T20 BOM-prefixed minimal JSON accepted", pb === true);

    check("T21 no page errors", pageErrors.length === 0, pageErrors.join(" ; "));

    const failed = results.filter((r) => !r.pass).length;
    console.log(failed === 0 ? "UI TEST: ALL PASSED (" + results.length + ")" : "UI TEST: " + failed + " FAILED");
    exitCode = failed === 0 ? 0 : 1;
  } catch (e) {
    console.log("UI TEST ERROR: " + (e && e.stack || e));
    exitCode = 1;
  }
  app.exit(exitCode);
});
