# Installing Kusha Costing App for One-Click Use

## Easiest internal use

### Mac
Double-click:

`Run_Kusha_Costing_App.command`

The first launch may take a few minutes because it creates a Python environment and installs Streamlit. Later launches are faster.

If macOS blocks it, right-click the file → Open.

### Windows
Double-click:

`Run_Kusha_Costing_App_Windows.bat`

Python 3 must be installed first, with "Add Python to PATH" enabled.

## True software installer

For a proper `.app` on Mac or `.exe` on Windows, ask a developer to package this project using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --name "Kusha Costing App" --onefile launcher.py
```

A production-grade version should eventually move to:

- Backend: FastAPI or Django
- Frontend: React / Next.js
- Database: PostgreSQL
- Hosting: AWS / Render / Railway / DigitalOcean
- Login + roles + backups + audit logs

This Version 8 package is still a local internal app, but now includes one-click launchers for Mac and Windows.
