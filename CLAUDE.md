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
- **Exception propagation segfaults**: On macOS, unhandled Python exceptions that propagate out of PyQt5 signal handlers into Qt's C++ event loop cause segfaults. NEVER use `raise` inside signal handlers — always catch and log. This is the #1 cause of segfaults on macOS.
- **takeWidget() focus-out cascade**: `QScrollArea.takeWidget()` generates focus-out events on child widgets (especially `QDoubleSpinBox`). Always `clearFocus()` on the focused widget BEFORE calling `takeWidget()` to prevent signal handlers firing during widget reparenting.
- **Matplotlib is NOT thread-safe**: `FigureCanvasQTAgg.draw()` must only be called from the main thread. The `FlatCAMObj.visible` property used to dispatch to a worker thread via `worker_task.emit()` — this caused segfaults when combined with main-thread canvas operations. In legacy mode, all canvas operations must be synchronous on the main thread.
- **Multiprocessing pool disabled**: `self.pool = None` on macOS arm64 due to segfault issues with the spawn context. Code that accesses the pool must check for None.
- **VisPy disabled**: VisPy patches and 3D engine are disabled on macOS arm64. The app always uses legacy (Matplotlib) 2D canvas.
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

### Double-click on Excellon file in Projects causes segfault
**Files**: `appObjects/ObjectCollection.py`, `appObjects/FlatCAMObj.py`, `appObjects/FlatCAMExcellon.py`
**Problem**: Double-clicking an Excellon object in the project tree caused a segfault on macOS.
**Root causes**:
1. `on_item_activated()` caught exceptions from `build_ui()` but re-raised them with `raise`,
   letting the exception propagate into Qt's C++ event loop — segfault on macOS.
2. `FlatCAMObj.build_ui()` called `takeWidget()` which triggers focus-out events on child
   widgets (FCDoubleSpinner), firing signal handlers during widget reparenting.
3. No exception guards on `build_ui()` call in `on_list_selection_change()`.
**Fix**: Removed `raise` from `on_item_activated()`, added `clearFocus()` before `takeWidget()`,
wrapped `build_ui()` calls in exception handlers, added guard for `self.ui is None`.

### Segfault when entering Excellon/Geometry editor on macOS
**Files**: `appEditors/AppExcEditor.py`, `appEditors/AppGeoEditor.py`, `appObjects/FlatCAMObj.py`
**Problem**: Entering the Excellon or Geometry editor crashed with segfault on macOS.
**Root cause**: `FlatCAMObj.visible` property setter always dispatches visibility changes to a
worker thread via `worker_task.emit()`. The worker thread then calls `axes.cla()` and
`canvas.draw()` on the shared matplotlib `FigureCanvasQTAgg` — but matplotlib is NOT thread-safe.
Meanwhile, the main thread continues with `replot()` which also calls `canvas.draw()`.
Two threads hitting `canvas.draw()` simultaneously causes the segfault.
**Fix**: In legacy (matplotlib) mode, run visibility changes synchronously on the main thread.
Also changed editor activate/deactivate to use direct `shapes.visible` instead of the
threaded property setter.
