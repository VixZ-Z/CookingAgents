"""Windows one-file build, including the gameplay music."""
from pathlib import Path

game_dir = Path(SPECPATH)

analysis = Analysis(
    [str(game_dir / "launcher.py")],
    pathex=[str(game_dir)],
    datas=[(str(game_dir / "assets"), "assets")],
    hiddenimports=[],
    excludes=[],
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="CookingAgents",
    console=False,
    debug=False,
    strip=False,
    upx=False,
)
