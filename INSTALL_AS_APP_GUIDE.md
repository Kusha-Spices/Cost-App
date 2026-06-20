# Installing the Kusha Costing App on a Mac

There are two ways to get a real, double-click Mac app. Option 1 needs nothing
installed and is recommended.

## Option 1 — Download the ready-made app (recommended, no Python, no Terminal)

The app is built automatically on real Macs by GitHub Actions.

1. Go to the repository on GitHub → **Actions** tab.
2. Open the latest **"Build macOS app"** run (or run it once with **Run workflow**).
3. Under **Artifacts**, download the one for your Mac:
   - **Apple Silicon** (M1/M2/M3/M4 — most Macs since 2021), or
   - **Intel** (older Macs).
   Not sure?  → Apple menu → *About This Mac*. "Apple M…" = Apple Silicon.
4. Unzip the download. You get **Kusha Costing App.app**.
5. Drag it into your **Applications** folder.
6. **First launch only:** right-click the app → **Open** → **Open** in the dialog.
   (macOS shows this prompt because the app is not paid-Apple-signed. After the
   first time, just double-click it normally.)

The app opens in your web browser. Your data is saved on your Mac at
`~/Library/Application Support/Kusha Costing App/` and is kept between updates.

### Publishing a downloadable version for everyone

Push a tag and the same build is attached to a GitHub **Release** that anyone can
download:

```bash
git tag v9.0
git push origin v9.0
```

## Option 2 — Build it yourself on a Mac (one Terminal command)

If you have a Mac with Python 3 and prefer to build locally:

```bash
bash scripts/build_mac_app.sh
```

The finished **Kusha Costing App.app** is left in the `dist/` folder. Drag it to
Applications and open it the same way as above.

## Quick run without building (developer / testing)

```bash
pip install -r requirements.txt
python run_app.py        # opens the browser automatically
# or
streamlit run app.py     # classic Streamlit run
```

## Notes

- The downloadable app bundles Python and every dependency — users need nothing
  installed.
- It is not yet notarized with an Apple Developer account, which is why the first
  launch needs the right-click → Open step. Adding notarization later removes that
  prompt; it requires a paid Apple Developer account and can be wired into the
  same GitHub Actions workflow.
- A Windows build can be produced from the same `KushaCostingApp.spec` using
  PyInstaller on a Windows machine.
