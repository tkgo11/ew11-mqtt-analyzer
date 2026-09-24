# PyInstaller spec — builds a single-folder binary bundling the built frontend.
# Requires: pip install -e . pyinstaller  &&  frontend/dist built first.
import pathlib

ROOT = pathlib.Path(SPECPATH)  # noqa: F821
DIST = ROOT / "frontend" / "dist"

datas = []
if DIST.is_dir():
    # resolve_static_dir() checks sys._MEIPASS / "static" first in frozen builds
    datas.append((str(DIST), "static"))

a = Analysis(  # noqa: F821
    ["src/ew11_analyzer/__main__.py"],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["uvicorn.lifespan.on", "uvicorn.protocols.websockets.auto"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ew11-analyzer",
    console=True,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="ew11-analyzer",
)
