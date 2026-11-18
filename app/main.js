"use strict";
/*
 * Moni desktop app — the Electron shell that makes the viewer a desktop
 * application (the canonical product form of Moni).
 *
 * The viewer itself stays exactly what it has always been: a single,
 * self-contained index.html with no external resources and no network
 * access. This shell only hosts that file in a window. The renderer gets
 * no Node.js access (contextIsolation on, nodeIntegration off, sandbox
 * on) and there is no preload script, so the viewer's behavior — and its
 * read-only, offline guarantees — are unchanged from browser use.
 *
 * A report file can be handed to the app as a command-line argument
 * (e.g. `Moni moni-report.json`); its contents are passed to the
 * viewer's own window.Moni.parseAndLoad(), so a malformed file is
 * rejected by the viewer with its usual in-page error message.
 */
const { app, BrowserWindow, dialog } = require("electron");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const VIEWER = path.join(__dirname, "..", "index.html");
const VIEWER_URL = pathToFileURL(VIEWER).href;

function reportPathFromArgv(argv) {
  for (const arg of argv.slice(1)) {
    if (typeof arg === "string" && !arg.startsWith("-") && arg.toLowerCase().endsWith(".json")) {
      return arg;
    }
  }
  return null;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 900,
    minWidth: 720,
    minHeight: 480,
    title: "Moni — PC Device Info Viewer",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  /* The viewer is a local file and never links out; keep it that way. */
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event, url) => {
    if (url !== VIEWER_URL) event.preventDefault();
  });

  const reportPath = reportPathFromArgv(process.argv);
  win.webContents.once("did-finish-load", async () => {
    console.log("Moni desktop: viewer loaded");
    if (!reportPath) return;
    let text;
    try {
      text = fs.readFileSync(reportPath, "utf8");
    } catch (err) {
      console.error("Moni desktop: could not read report file " + reportPath + ": " + err.message);
      dialog.showErrorBox("Moni", "Could not read the report file:\n" + reportPath);
      return;
    }
    try {
      const accepted = await win.webContents.executeJavaScript(
        "window.Moni && window.Moni.parseAndLoad(" + JSON.stringify(text) + ")", true);
      console.log("Moni desktop: report " + reportPath + " handed to viewer (accepted: " + accepted + ")");
    } catch (err) {
      console.error("Moni desktop: failed to hand the report to the viewer: " + err.message);
    }
  });

  win.loadFile(VIEWER);
  return win;
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
