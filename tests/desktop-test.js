"use strict";

const { app } = require("electron");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");

const scenario = process.argv[2];
const valid = scenario === "valid";
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "moni-desktop-test-"));
const reportPath = path.join(tmp, "test report.json");
if (valid) {
  fs.copyFileSync(path.join(__dirname, "..", "sample-report.json"), reportPath);
} else {
  fs.writeFileSync(reportPath, "{not json");
}
app.setPath("userData", tmp);
app.disableHardwareAcceleration();
process.argv.splice(2, 1, reportPath);
process.on("exit", () => {
  try { fs.rmSync(tmp, { recursive: true, force: true, maxRetries: 3 }); }
  catch (error) { console.warn("Could not remove the temporary desktop test directory:", error.code); }
});

function fail(message) {
  console.error("FAIL | " + scenario + " report: " + message);
  app.exit(1);
}

setTimeout(() => fail("viewer did not reach the expected state"), 20000);

app.once("browser-window-created", (_event, win) => {
  const contents = win.webContents;
  contents.once("did-fail-load", (_error, code, description) => fail(code + " " + description));
  contents.once("render-process-gone", (_event, details) => fail(details.reason));
  contents.once("did-finish-load", async () => {
    try {
      while (!contents.isDestroyed()) {
        const state = await contents.executeJavaScript(`({
          samplesShown: document.querySelector("#cards").textContent.includes("SAMPLE-DESKTOP"),
          cardCount: document.querySelectorAll("#cards .card").length,
          errorShown: document.querySelector("#errBanner").style.display === "block",
        })`);
        if (valid ? state.samplesShown && state.cardCount === 10 && !state.errorShown
                  : state.errorShown && state.cardCount === 0) {
          console.log("PASS | " + scenario + " report");
          app.exit(0);
          return;
        }
        await delay(50);
      }
      fail("viewer closed before the check completed");
    } catch (error) {
      fail(error.message);
    }
  });
});

// Use the production desktop entry point with the fixture passed as a launch argument.
require("../app/main");
