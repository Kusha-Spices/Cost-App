/* Secure bridge between the renderer (the studio UI) and Electron.
   Exposes a tiny, safe `window.aurora` API — no Node access leaks to the page. */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("aurora", {
  isDesktop: true,
  platform: process.platform,
  minimize: () => ipcRenderer.invoke("win:minimize"),
  maximize: () => ipcRenderer.invoke("win:maximize"),
  close: () => ipcRenderer.invoke("win:close"),
  isMaximized: () => ipcRenderer.invoke("win:isMaximized"),
  onMaximized: (cb) => ipcRenderer.on("win:maximized", (_e, v) => cb(v)),
  onMenu: (cb) => {
    ipcRenderer.on("menu:new", () => cb("new"));
  },
});
