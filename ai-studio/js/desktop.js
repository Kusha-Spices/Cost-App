/* ============================================================================
   AURORA · desktop.js — native-window integration.
   No-ops in a plain browser; only activates when running inside Electron
   (where the preload bridge `window.aurora` exists).
   ========================================================================== */
(function () {
  "use strict";
  const A = window.aurora;
  if (!A || !A.isDesktop) return; // web build → leave everything as-is

  const body = document.body;
  body.classList.add("desktop");
  if (A.platform === "darwin") body.classList.add("is-mac");      // native traffic lights
  else body.classList.add("is-win", "has-winctl");               // custom window controls

  const $ = (id) => document.getElementById(id);
  const min = $("wcMin"), max = $("wcMax"), close = $("wcClose");
  if (min) min.onclick = () => A.minimize();
  if (max) max.onclick = () => A.maximize();
  if (close) close.onclick = () => A.close();

  if (A.onMaximized) A.onMaximized((isMax) => body.classList.toggle("is-max", !!isMax));
  if (A.isMaximized) A.isMaximized().then((v) => body.classList.toggle("is-max", !!v));

  if (A.onMenu) A.onMenu((action) => {
    if (action === "new" && window.Aurora && window.Aurora.Engine) {
      window.Aurora.Engine.clearLayers();
    }
  });
})();
