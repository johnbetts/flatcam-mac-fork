# FlatCAM - Claude Code Project Guide

## Project Overview
FlatCAM is a 2D Computer-Aided PCB Manufacturing application for CNC routers.
It converts Gerber/Excellon PCB files into G-code for CNC milling.

- **Version**: 2024.4 (Beta)
- **Upstream**: https://github.com/vika-sonne/FlatCAM.git
- **GUI Framework**: PyQt5 5.15.2
- **Python**: 3.10.x only (strict requirement in pyproject.toml)
- **Graphics**: VisPy 0.6.6 (modern) + PlotCanvasLegacy (Matplotlib fallback)
- **Geometry**: Shapely 1.8.4, NumPy 1.22

## Project Structure
```
FlatCAM/
  FlatCAM.py          # Entry point (main function)
  app_Main.py         # Core App class (~10K lines)
  camlib.py           # Central geometry library (~310K)
  defaults.py         # Configuration defaults
  appEditors/         # Editor modules (Excellon, Geometry, Gerber, GCode)
  appGUI/             # GUI components (MainGUI, GUIElements, PlotCanvas)
  appTools/           # 37 CAM tools (Drilling, Isolation, NCC, Paint, etc.)
  appObjects/         # Data objects (Excellon, Gerber, CNCJob, Geometry)
  appCommon/          # Common utilities
  appParsers/         # File format parsers (Excellon, Gerber, DXF, SVG, etc.)
  tclCommands/        # TCL scripting interface
  preprocessors/      # CNC preprocessor modules
  pyproject.toml      # Poetry configuration
  requirements.txt    # Pip dependencies (with hashes)
```

## Running the Application
```bash
cd /Users/johnbetts/tmp/FlatCAM
python -m FlatCAM
```

## Key Development Notes

### Common Crash Patterns
- **PyQt5 signal/slot issues**: Always guard `currentItem()`, `currentRow()` etc. — they can return `None` when focus is lost or selection is cleared.
- **Shapely deprecation**: Iterating multi-part geometries (MultiLineString, MultiPolygon) directly is deprecated. Use `.geoms` accessor instead (e.g., `for geo in multi.geoms:`).
- **Table widget summary rows**: The Excellon editor tools table has 2 extra rows at the bottom (Total Drills, Total Slots) that are non-editable. Always validate row indices against `tool2tooldia` before lookup.
- **Signal reconnection**: When disconnecting signals in handlers (to prevent re-entrant calls), always reconnect them in ALL exit paths (including early returns and error handling).

### macOS-Specific Issues
- OpenGL/VisPy rendering may need patches (see `appGUI/VisPyPatches.py`)
- PlotCanvasLegacy has macOS-specific draw handling (see `appGUI/PlotCanvasLegacy.py`)

### Editing Conventions
- Tabs for indentation (not spaces)
- PyQt5 signal/slot pattern throughout
- Defensive try/except blocks around UI operations
- Logging via module-level `log` variable (from `appLogger`)

## Bugs Fixed (Local)

### Excellon Editor drill size crash
**File**: `appEditors/AppExcEditor.py` — `on_tool_edit()`
**Problem**: Clicking a drill size value then clicking elsewhere crashed the app.
`currentItem()` returned `None` causing `AttributeError` (only `ValueError` was caught).
Also, clicking on summary rows caused `KeyError` in `tool2tooldia` lookup.
**Fix**: Added `None` check for `currentItem()`, validate row index against `tool2tooldia`,
and reconnect signals in all early-return paths.
