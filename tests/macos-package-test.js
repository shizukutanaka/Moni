"use strict";

const { execFileSync, spawn } = require("node:child_process");
const { copyFileSync, mkdtempSync, rmSync, writeFileSync } = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");

function checkReport(executable, report, profile, accepted) {
  return new Promise((resolve, reject) => {
    const app = spawn(executable, ["--user-data-dir=" + profile, report], {
      stdio: ["ignore", "pipe", "inherit"],
      timeout: 20000,
      killSignal: "SIGKILL"
    });
    const resultPrefix = "Moni desktop: report " + report + " handed to viewer (accepted: ";
    let result;
    const stdout = readline.createInterface({ input: app.stdout });
    stdout.on("line", (line) => {
      if (line.startsWith(resultPrefix)) {
        result = line.slice(resultPrefix.length, -1);
        app.kill("SIGKILL");
      }
    });
    app.once("error", reject);
    app.once("close", (code, signal) => {
      if (result === String(accepted)) resolve();
      else if (result !== undefined) reject(new Error("Expected acceptance " + accepted + ", got " + result));
      else reject(new Error("Packaged Moni stopped without a viewer result: " + (signal || code)));
    });
  });
}

async function main() {
  const [archive, ...extra] = process.argv.slice(2);
  if (!archive || extra.length || !archive.endsWith(".zip")) {
    throw new Error("Expected exactly one macOS release ZIP");
  }

  const tmp = mkdtempSync(path.join(os.tmpdir(), "moni-macos-package-"));
  try {
    execFileSync("ditto", ["-x", "-k", archive, tmp], { stdio: "inherit" });
    const executable = path.join(tmp, "Moni.app", "Contents", "MacOS", "Moni");
    const valid = path.join(tmp, "valid report.json");
    const invalid = path.join(tmp, "invalid report.json");
    copyFileSync(path.join(__dirname, "..", "sample-report.json"), valid);
    writeFileSync(invalid, "{not json");

    await checkReport(executable, valid, path.join(tmp, "valid-profile"), true);
    console.log("PASS | Packaged Moni accepts a valid report");
    await checkReport(executable, invalid, path.join(tmp, "invalid-profile"), false);
    console.log("PASS | Packaged Moni rejects malformed JSON");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
