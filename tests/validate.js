"use strict";
/*
 * Moni static + schema validation (Node.js, no dependencies).
 *
 * Checks:
 *  1. sample-report.json conforms to the moni-report schema.
 *  2. The SAMPLE_REPORT embedded in index.html is identical to sample-report.json.
 *  3. index.html references no external resources (offline, single file).
 *  4. collect.ps1 is UTF-16LE with BOM, emits every schema key, and contains
 *     no network-sending commands (read-only collector).
 *  5. collect.bat is ASCII-only, calls collect.ps1 and pauses.
 *  6. README.md documents the Moni / BIOSMAN split.
 *  7. collect.sh (Linux) emits every schema key, contains no network or
 *     system-changing commands, passes bash -n, and — on Linux — a live
 *     run in a temp dir produces a schema-valid report.
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
let failures = 0;
function check(name, cond, detail) {
  if (cond) { console.log("PASS | " + name); }
  else { failures++; console.log("FAIL | " + name + (detail ? " | " + detail : "")); }
}
const isNil = (v) => v === null || v === undefined;
const isNStr = (v) => isNil(v) || typeof v === "string";
const isNNum = (v) => isNil(v) || (typeof v === "number" && Number.isFinite(v));

function validateReport(rep) {
  const errs = [];
  const need = (cond, msg) => { if (!cond) errs.push(msg); };
  need(rep && typeof rep === "object", "report must be an object");
  if (!rep || typeof rep !== "object") return errs;
  need(rep.format === "moni-report", "format must be 'moni-report'");
  need(rep.version === 1, "version must be 1");
  need(typeof rep.collectedAt === "string", "collectedAt must be a string");
  need(typeof rep.collector === "string", "collector must be a string");
  need(typeof rep.sampleData === "boolean", "sampleData must be a boolean");

  const s = rep.system || {};
  ["computerName", "manufacturer", "model", "osName", "osVersion", "osBuild"].forEach((k) => need(isNStr(s[k]), "system." + k));
  need(isNNum(s.uptimeSeconds), "system.uptimeSeconds");

  const c = rep.cpu || {};
  need(isNStr(c.name), "cpu.name");
  ["cores", "logicalProcessors", "maxClockMHz"].forEach((k) => need(isNNum(c[k]), "cpu." + k));

  const m = rep.memory || {};
  need(isNNum(m.totalBytes), "memory.totalBytes");
  need(Array.isArray(m.modules), "memory.modules must be an array");
  (m.modules || []).forEach((mod, i) => {
    need(isNNum(mod.capacityBytes), "memory.modules[" + i + "].capacityBytes");
    need(isNStr(mod.type), "memory.modules[" + i + "].type");
    need(isNNum(mod.speedMHz), "memory.modules[" + i + "].speedMHz");
    need(isNStr(mod.manufacturer), "memory.modules[" + i + "].manufacturer");
    need(isNStr(mod.partNumber), "memory.modules[" + i + "].partNumber");
  });

  need(Array.isArray(rep.gpus), "gpus must be an array");
  (rep.gpus || []).forEach((g, i) => {
    need(isNStr(g.name), "gpus[" + i + "].name");
    need(isNNum(g.vramBytes), "gpus[" + i + "].vramBytes");
    need(isNStr(g.driverVersion), "gpus[" + i + "].driverVersion");
  });

  const mb = rep.motherboard || {};
  ["manufacturer", "product", "biosVersion", "biosDate"].forEach((k) => need(isNStr(mb[k]), "motherboard." + k));

  const st = rep.storage || {};
  need(Array.isArray(st.physical), "storage.physical must be an array");
  (st.physical || []).forEach((d, i) => {
    need(isNStr(d.model), "storage.physical[" + i + "].model");
    need(isNNum(d.sizeBytes), "storage.physical[" + i + "].sizeBytes");
    need(isNStr(d.mediaType), "storage.physical[" + i + "].mediaType");
    need(isNStr(d.busType), "storage.physical[" + i + "].busType");
  });
  need(Array.isArray(st.logical), "storage.logical must be an array");
  (st.logical || []).forEach((d, i) => {
    need(isNStr(d.drive), "storage.logical[" + i + "].drive");
    need(isNStr(d.label), "storage.logical[" + i + "].label");
    need(isNStr(d.fileSystem), "storage.logical[" + i + "].fileSystem");
    need(isNNum(d.totalBytes), "storage.logical[" + i + "].totalBytes");
    need(isNNum(d.freeBytes), "storage.logical[" + i + "].freeBytes");
  });

  need(Array.isArray(rep.network), "network must be an array");
  (rep.network || []).forEach((n, i) => {
    need(isNStr(n.name), "network[" + i + "].name");
    need(isNStr(n.description), "network[" + i + "].description");
    need(isNStr(n.status), "network[" + i + "].status");
    need(Array.isArray(n.ipv4) && n.ipv4.every((x) => typeof x === "string"), "network[" + i + "].ipv4");
    need(Array.isArray(n.ipv6) && n.ipv6.every((x) => typeof x === "string"), "network[" + i + "].ipv6");
    need(isNStr(n.macAddress), "network[" + i + "].macAddress");
    need(isNNum(n.linkSpeedMbps), "network[" + i + "].linkSpeedMbps");
  });

  need(Array.isArray(rep.displays), "displays must be an array");
  (rep.displays || []).forEach((d, i) => {
    need(isNStr(d.name), "displays[" + i + "].name");
    need(isNNum(d.width), "displays[" + i + "].width");
    need(isNNum(d.height), "displays[" + i + "].height");
    need(isNNum(d.refreshRateHz), "displays[" + i + "].refreshRateHz");
  });

  if (!isNil(rep.battery)) {
    const b = rep.battery;
    need(isNNum(b.chargePercent), "battery.chargePercent");
    need(isNStr(b.status), "battery.status");
    need(isNNum(b.designCapacityMWh), "battery.designCapacityMWh");
    need(isNNum(b.fullChargeCapacityMWh), "battery.fullChargeCapacityMWh");
  }

  need(Array.isArray(rep.peripherals), "peripherals must be an array");
  (rep.peripherals || []).forEach((p, i) => {
    need(isNStr(p.name), "peripherals[" + i + "].name");
    need(isNStr(p.description), "peripherals[" + i + "].description");
  });
  return errs;
}

/* 1. sample schema */
const sample = JSON.parse(fs.readFileSync(path.join(root, "sample-report.json"), "utf8"));
const schemaErrs = validateReport(sample);
check("sample-report.json conforms to schema", schemaErrs.length === 0, schemaErrs.join("; "));
check("sample-report.json is marked as sample data", sample.sampleData === true);

/* 2. embedded sample in index.html */
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const m = html.match(/const SAMPLE_REPORT = (\{.*?\});\n/s);
check("index.html embeds SAMPLE_REPORT", !!m);
if (m) {
  const embedded = JSON.parse(m[1]);
  const canonical = (v) => Array.isArray(v) ? v.map(canonical)
    : (v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canonical(v[k])])) : v);
  check("embedded sample matches sample-report.json",
    JSON.stringify(canonical(embedded)) === JSON.stringify(canonical(sample)));
}

/* 3. no external resources in index.html */
const externalRefs = html.match(/<(?:script|link|img|iframe)[^>]+(?:src|href)\s*=\s*"https?:[^"]*"/gi) || [];
check("index.html has no external resource references", externalRefs.length === 0, externalRefs.join(", "));
check("index.html has no fetch/XHR network calls", !/fetch\(|XMLHttpRequest|WebSocket/.test(html));

/* 4. collect.ps1 */
const ps1Buf = fs.readFileSync(path.join(root, "collect.ps1"));
check("collect.ps1 starts with UTF-16LE BOM", ps1Buf[0] === 0xff && ps1Buf[1] === 0xfe);
const ps1 = ps1Buf.toString("utf16le");
const schemaKeys = ["computerName", "manufacturer", "model", "osName", "osVersion", "osBuild",
  "uptimeSeconds", "cores", "logicalProcessors", "maxClockMHz", "totalBytes", "modules",
  "capacityBytes", "speedMHz", "partNumber", "vramBytes", "driverVersion", "biosVersion",
  "biosDate", "physical", "logical", "drive", "fileSystem", "freeBytes", "ipv4", "ipv6",
  "macAddress", "linkSpeedMbps", "width", "height", "refreshRateHz", "chargePercent",
  "designCapacityMWh", "fullChargeCapacityMWh", "peripherals", "moni-report", "collectedAt"];
const missingKeys = schemaKeys.filter((k) => !ps1.includes(k));
check("collect.ps1 emits all schema keys", missingKeys.length === 0, "missing: " + missingKeys.join(", "));
const forbidden = ["Invoke-WebRequest", "Invoke-RestMethod", "Start-BitsTransfer", "Send-MailMessage",
  "Net.WebClient", "WebRequest", "HttpClient", "curl.exe", "ftp.exe", "Test-Connection", "Send-"];
const foundForbidden = forbidden.filter((f) => ps1.includes(f));
check("collect.ps1 contains no network-sending commands", foundForbidden.length === 0, "found: " + foundForbidden.join(", "));
check("collect.ps1 writes moni-report.json", ps1.includes("moni-report.json"));
const opens = (ps1.match(/\{/g) || []).length, closes = (ps1.match(/\}/g) || []).length;
check("collect.ps1 braces balance", opens === closes, opens + " vs " + closes);
const po = (ps1.match(/\(/g) || []).length, pc = (ps1.match(/\)/g) || []).length;
check("collect.ps1 parentheses balance", po === pc, po + " vs " + pc);

/* 5. collect.bat */
const bat = fs.readFileSync(path.join(root, "collect.bat"));
const batText = bat.toString("latin1");
check("collect.bat is ASCII-only", bat.every((b) => b < 128));
check("collect.bat calls collect.ps1", batText.includes("collect.ps1"));
check("collect.bat has a pause", /pause/.test(batText));

/* 6. README */
const readme = fs.readFileSync(path.join(root, "README.md"), "utf8");
check("README documents the BIOSMAN split", readme.includes("BIOSMAN"));
check("README states what Moni does NOT do", /やらないこと|does NOT|does not do/i.test(readme));
check("README documents the Linux collector", readme.includes("collect.sh"));

/* 7. collect.sh (Linux collector) */
const shPath = path.join(root, "collect.sh");
check("collect.sh exists", fs.existsSync(shPath));
if (fs.existsSync(shPath)) {
  const sh = fs.readFileSync(shPath, "utf8");
  check("collect.sh has a bash shebang", sh.startsWith("#!/usr/bin/env bash") || sh.startsWith("#!/bin/bash"));
  check("collect.sh is executable", (fs.statSync(shPath).mode & 0o111) !== 0);
  const missingShKeys = schemaKeys.filter((k) => !sh.includes(k));
  check("collect.sh emits all schema keys", missingShKeys.length === 0, "missing: " + missingShKeys.join(", "));
  const forbiddenNet = ["curl", "wget", "/dev/tcp", "netcat", "socat", "telnet", "Invoke-WebRequest"];
  const foundNet = forbiddenNet.filter((f) => sh.includes(f));
  check("collect.sh contains no network-sending commands", foundNet.length === 0, "found: " + foundNet.join(", "));
  const forbiddenWrite = ["mkfs", "fdisk", "parted", "systemctl", "shutdown", "reboot", "apt-get", "dnf install", "pacman -", "dd if=", "umount"];
  const foundWrite = forbiddenWrite.filter((f) => sh.includes(f));
  check("collect.sh contains no system-changing commands", foundWrite.length === 0, "found: " + foundWrite.join(", "));
  check("collect.sh writes moni-report.json", sh.includes("moni-report.json"));
  let syntaxOk = false, syntaxDetail = "";
  try {
    require("child_process").execFileSync("bash", ["-n", shPath], { stdio: "pipe" });
    syntaxOk = true;
  } catch (e) { syntaxDetail = String((e && e.stderr) || e); }
  check("collect.sh passes bash -n", syntaxOk, syntaxDetail.slice(0, 200));

  if (process.platform === "linux") {
    const tmp = fs.mkdtempSync(path.join(require("os").tmpdir(), "moni-collect-"));
    try {
      fs.copyFileSync(shPath, path.join(tmp, "collect.sh"));
      require("child_process").execFileSync("bash", [path.join(tmp, "collect.sh")], { stdio: "pipe", timeout: 60000 });
      const live = JSON.parse(fs.readFileSync(path.join(tmp, "moni-report.json"), "utf8"));
      const liveErrs = validateReport(live);
      check("collect.sh live run produces a schema-valid report", liveErrs.length === 0, liveErrs.join("; "));
      check("live report is real data from collect.sh",
        live.sampleData === false && typeof live.collector === "string" && live.collector.includes("collect.sh"));
    } catch (e) {
      check("collect.sh live run produces a schema-valid report", false, String((e && e.message) || e).slice(0, 200));
    } finally {
      try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (_) {}
    }
  }
}

console.log(failures === 0 ? "\nALL CHECKS PASSED" : "\n" + failures + " CHECK(S) FAILED");
process.exit(failures === 0 ? 0 : 1);
