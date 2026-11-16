"use strict";
/*
 * Moni viewer UI test — drives index.html in Electron (headless via Xvfb).
 * Verifies: no page errors, sample renders all 10 category cards, null items
 * are shown honestly ("取得不可"), battery=null shows "なし", search filters,
 * language switch re-renders in English, text export is generated, report
 * diff (changes detected, volatile fields excluded, panel UI) and masked
 * share export (fields hidden, original untouched, dialog defaults).
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

    /* Diff: sample (before) vs a modified copy (after) */
    await js(`window.Moni.setLang('ja'); window.Moni.loadSample(); 'ok'`);
    await sleep(300);
    const beforeRep = await js(`window.Moni.getReport()`);
    const afterRep = JSON.parse(JSON.stringify(beforeRep));
    afterRep.collectedAt = "2026-02-01T10:30:00+09:00";
    afterRep.motherboard.biosVersion = "1.30";
    afterRep.gpus[0].driverVersion = "32.0.15.9999";
    afterRep.peripherals = afterRep.peripherals.filter((p) => !p.name.includes("Mouse"));
    afterRep.displays.push({ name: "Sample Display 32 (fictional)", width: 3840, height: 2160, refreshRateHz: 60 });
    afterRep.system.uptimeSeconds = 12345;              /* excluded from diff */
    afterRep.storage.logical[0].freeBytes = 1000;       /* excluded from diff */
    const d1 = await js(`window.Moni.diffReports(${JSON.stringify(beforeRep)}, ${JSON.stringify(afterRep)})`);
    const biosChange = (d1.changes || []).find((c) => c.key === "motherboard.biosVersion");
    check("T22 diff detects BIOS version change", !!biosChange && biosChange.type === "changed" && biosChange.before === "1.20" && biosChange.after === "1.30",
      JSON.stringify(biosChange || null));
    check("T23 diff detects driver change, peripheral removal, display addition (device add collapses to one entry)",
      d1.changes.some((c) => c.type === "changed" && c.key.endsWith(".driverVersion")) &&
      d1.changes.some((c) => c.type === "removed" && c.key.startsWith("peripheral|")) &&
      d1.changes.some((c) => c.type === "added" && c.key.startsWith("display|")) &&
      d1.changes.filter((c) => c.type === "added").every((c) => !/\.(resolution|refreshRateHz)$/.test(c.key)),
      (d1.changes || []).map((c) => c.type + ":" + c.key).join(", "));
    const dSame = await js(`window.Moni.diffReports(${JSON.stringify(beforeRep)}, ${JSON.stringify(beforeRep)})`);
    check("T24 excluded fields ignored; identical reports have no changes",
      d1.changes.every((c) => !c.key.includes("uptime") && !c.key.includes("freeBytes")) &&
      dSame.changes.length === 0 && dSame.unchanged.length > 0,
      "same-changes=" + (dSame.changes || []).length + " unchanged=" + (dSame.unchanged || []).length);

    /* Compare UI: panel renders, unchanged collapsed, main view shows "after" */
    await js(`window.Moni.setCompare(${JSON.stringify(beforeRep)}, ${JSON.stringify(afterRep)}); 'ok'`);
    await sleep(300);
    let dui = await js(`({
      shown: document.getElementById('diffArea').style.display !== 'none',
      text: document.getElementById('diffArea').textContent,
      hasDetails: !!document.querySelector('#diffArea details'),
      cmp: window.Moni.getCompare(),
      mainText: document.getElementById('cards').textContent
    })`);
    check("T25 compare panel shows changes and collapsed unchanged list",
      dui.shown === true && dui.text.includes("レポート比較") && dui.text.includes("1.30") &&
      dui.text.includes("Sample Wireless Mouse") && dui.hasDetails === true,
      dui.text.slice(0, 120));
    check("T26 compare orders by collectedAt and main view shows the after report",
      !!dui.cmp && dui.cmp.before.collectedAt === "2026-01-15T10:30:00+09:00" &&
      dui.cmp.after.collectedAt === "2026-02-01T10:30:00+09:00" && dui.mainText.includes("1.30"), "");
    await js(`document.getElementById('btnDiffClose').click(); 'ok'`);
    await sleep(200);
    check("T27 compare panel closes", await js(`document.getElementById('diffArea').style.display`) === "none");

    /* Masked share export */
    const masked = await js(`window.Moni.maskReport(window.Moni.getReport())`);
    const origAfter = await js(`window.Moni.getReport()`);
    check("T28 maskReport hides computer name, MAC and IP addresses by field",
      masked.system.computerName === "(masked)" &&
      masked.network[0].macAddress === "(masked)" &&
      masked.network[0].ipv4[0] === "(masked)" &&
      masked.network[0].ipv6[0] === "(masked)", JSON.stringify(masked.network && masked.network[0]));
    check("T29 maskReport leaves original and non-identifier fields untouched, keeps nulls",
      origAfter.system.computerName === "SAMPLE-DESKTOP" &&
      masked.gpus[0].name === origAfter.gpus[0].name &&
      masked.gpus[1].vramBytes === null, "");
    const mtxt = await js(`window.Moni.buildTextExport(${JSON.stringify(masked)}, { masked: true })`);
    check("T30 masked text export is marked and leaks no identifier values",
      typeof mtxt === "string" && mtxt.includes("(masked)") && mtxt.includes("マスク済み") &&
      !mtxt.includes("AA-BB-CC-DD-EE-FF") && !mtxt.includes("SAMPLE-DESKTOP") && !mtxt.includes("192.168.1.50"),
      (mtxt || "").slice(0, 120));

    /* Share dialog: masked by default, unmasked choice shows what is included */
    await js(`document.getElementById('btnShareExport').click(); 'ok'`);
    await sleep(200);
    let sm = await js(`({
      shown: document.getElementById('shareModal').style.display === 'flex',
      mode: (document.querySelector('input[name="shareMask"]:checked') || {}).value,
      maskedInfo: document.getElementById('shareMaskedInfo').style.display !== 'none',
      fullInfo: document.getElementById('shareFullInfo').style.display !== 'none'
    })`);
    check("T31 share dialog defaults to masked with the hidden-items list shown",
      sm.shown === true && sm.mode === "masked" && sm.maskedInfo === true && sm.fullInfo === false, JSON.stringify(sm));
    await js(`{ const r = document.querySelector('input[name="shareMask"][value="full"]'); r.checked = true; r.dispatchEvent(new Event('change')); 'ok' }`);
    await sleep(200);
    let sm2 = await js(`({
      fullInfo: document.getElementById('shareFullInfo').style.display !== 'none',
      fullText: document.getElementById('shareFullInfo').textContent
    })`);
    check("T32 unmasked choice warns which items are included as-is",
      sm2.fullInfo === true && sm2.fullText.includes("MAC"), sm2.fullText.slice(0, 80));
    await js(`document.getElementById('btnShareCancel').click(); 'ok'`);
    await sleep(100);

    check("T33 no page errors", pageErrors.length === 0, pageErrors.join(" ; "));

    const failed = results.filter((r) => !r.pass).length;
    console.log(failed === 0 ? "UI TEST: ALL PASSED (" + results.length + ")" : "UI TEST: " + failed + " FAILED");
    exitCode = failed === 0 ? 0 : 1;
  } catch (e) {
    console.log("UI TEST ERROR: " + (e && e.stack || e));
    exitCode = 1;
  }
  app.exit(exitCode);
});
