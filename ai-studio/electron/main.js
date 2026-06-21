/* ============================================================================
   AURORA · Electron main process — turns the studio into a native desktop app.
   ========================================================================== */
const { app, BrowserWindow, Menu, ipcMain, shell, session } = require("electron");
const path = require("path");

const isMac = process.platform === "darwin";
const ROOT = path.join(__dirname, "..");
let win = null;

app.setName("Aurora Studio");

function createWindow() {
  win = new BrowserWindow({
    width: 1480,
    height: 920,
    minWidth: 1120,
    minHeight: 720,
    backgroundColor: "#07080f",      // matches the app shell → no white flash
    show: false,
    title: "Aurora Studio",
    icon: path.join(ROOT, "build", "icon.png"),
    // Frameless with a custom title bar. macOS keeps native traffic lights.
    titleBarStyle: isMac ? "hiddenInset" : "default",
    trafficLightPosition: isMac ? { x: 16, y: 20 } : undefined,
    frame: isMac ? true : false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  });

  win.loadFile(path.join(ROOT, "index.html"));
  win.once("ready-to-show", () => win.show());

  // Smoke mode (CI / verification): boot, report renderer errors, optionally
  // capture a screenshot, then quit.
  if (process.env.AURORA_SMOKE) {
    win.webContents.on("console-message", (_e, level, message) => {
      if (level >= 3) console.log("RENDERER-ERROR:", message);
    });
    win.webContents.on("render-process-gone", (_e, d) => { console.log("RENDER-GONE:", d.reason); app.exit(1); });
    win.webContents.on("did-finish-load", () => {
      console.log("AURORA_READY");
      const wait = process.env.AURORA_SHOT ? 4000 : 1500;
      setTimeout(async () => {
        if (process.env.AURORA_SCENARIO) {
          try {
            const r = await win.webContents.executeJavaScript(`(async()=>{const D=window.Aurora.Director;
              await D.handle('clear canvas');
              await D.handle('generate a neon city skyline at night');
              await D.handle('add a title that says "KUSHA SPICES"');
              await D.handle('make it cinematic');
              await D.handle('add a slow ken-burns zoom');
              window.Aurora.Engine.select(null);
              const d=window.Aurora.Engine.doc;
              return {layers:d.layers.length, types:d.layers.map(l=>l.type).join(',')};})()`);
            console.log("SCENARIO", JSON.stringify(r));
            await new Promise((res) => setTimeout(res, 1400));
          } catch (e) { console.log("SCENARIO-ERR", e.message); }
        }
        if (process.env.AURORA_DIAG) {
          try {
            const diag = await win.webContents.executeJavaScript(`(()=>{const A=window.Aurora,d=A&&A.Engine&&A.Engine.doc,bg=d&&d.layers.find(l=>l.type==='image'),el=bg&&A.Engine.els.get(bg.id);return{layers:d?d.layers.length:-1,bgSrcLen:bg?(bg.src||'').length:-1,bgImg:el?getComputedStyle(el).backgroundImage.slice(0,30):'no-el',w:el?el.style.width:'-',stageKids:document.getElementById('stage').children.length};})()`);
            console.log("DIAG", JSON.stringify(diag));
          } catch (e) { console.log("DIAG-ERR", e.message); }
        }
        if (process.env.AURORA_SHOT) {
          try {
            const img = await win.webContents.capturePage();
            require("fs").writeFileSync(process.env.AURORA_SHOT, img.toPNG());
            console.log("AURORA_SHOT_SAVED");
          } catch (e) { console.log("SHOT_ERROR:", e.message); }
        }
        app.quit();
      }, wait);
    });
  }

  win.on("maximize", () => win.webContents.send("win:maximized", true));
  win.on("unmaximize", () => win.webContents.send("win:maximized", false));

  // open external links in the user's browser, never in-app
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  // grant microphone access so voice-to-voice works inside the app
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => {
    cb(["media", "microphone", "audioCapture"].includes(permission));
  });
  buildMenu();
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (!isMac) app.quit();
});

/* window-control IPC (used by the custom title bar on Windows/Linux) */
ipcMain.handle("win:minimize", () => win && win.minimize());
ipcMain.handle("win:maximize", () => {
  if (!win) return false;
  win.isMaximized() ? win.unmaximize() : win.maximize();
  return win.isMaximized();
});
ipcMain.handle("win:close", () => win && win.close());
ipcMain.handle("win:isMaximized", () => !!(win && win.isMaximized()));

/* Application menu. Note: we intentionally omit an Undo accelerator so the
   studio's own Ctrl/⌘+Z (custom history) keeps working in the renderer. */
function buildMenu() {
  const template = [];

  if (isMac) {
    template.push({
      label: app.name,
      submenu: [
        { role: "about" }, { type: "separator" },
        { role: "hide" }, { role: "hideOthers" }, { role: "unhide" },
        { type: "separator" }, { role: "quit" },
      ],
    });
  }

  template.push({
    label: "File",
    submenu: [
      { label: "New Project", accelerator: "CmdOrCtrl+N", click: () => win && win.webContents.send("menu:new") },
      { type: "separator" },
      isMac ? { role: "close" } : { role: "quit" },
    ],
  });

  template.push({
    label: "Edit",
    submenu: [
      { role: "cut" }, { role: "copy" }, { role: "paste" }, { role: "selectAll" },
    ],
  });

  template.push({
    label: "View",
    submenu: [
      { role: "reload" }, { role: "forceReload" }, { role: "toggleDevTools" },
      { type: "separator" },
      { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
      { type: "separator" }, { role: "togglefullscreen" },
    ],
  });

  template.push({
    label: "Window",
    submenu: [{ role: "minimize" }, { role: "zoom" }, ...(isMac ? [{ type: "separator" }, { role: "front" }] : [{ role: "close" }])],
  });

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
