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
- **Rapid canvas.draw() segfaults**: On macOS Qt5Agg backend, rapid successive `canvas.draw()` calls can cause segfaults. Use `PlotCanvasLegacy._batch_draw = True` to suppress intermediate draws during multi-step operations (like editor activation), then do a single `canvas.draw_idle()` at the end.
- **Qt signal disconnect()**: Always wrap `signal.disconnect()` in `try/except (TypeError, RuntimeError)`. Calling `disconnect()` with no connections raises TypeError which, if propagating from a signal handler, causes macOS segfaults.
- **Worker thread + deleted Qt widgets**: Worker threads that emit signals carrying Qt widget references (tree items, etc.) can deliver those signals after the widgets have been destroyed (e.g., when the user enters an editor). Always use `sip.isdeleted()` to check widget validity before accessing, and check `app.call_source` to skip work when in editor mode.
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
**Files**: `appEditors/AppExcEditor.py`, `appEditors/AppGeoEditor.py`, `appObjects/FlatCAMObj.py`,
`appGUI/PlotCanvasLegacy.py`, `app_Main.py`, `appEditors/AppGerberEditor.py`
**Problem**: Entering the Excellon or Geometry editor crashed with segfault on macOS.
**Root causes** (three separate issues, all contributing):

1. **Thread-unsafe canvas.draw()**: `FlatCAMObj.visible` property setter dispatched visibility
   changes to a worker thread via `worker_task.emit()`. The worker thread called `axes.cla()` and
   `canvas.draw()` while the main thread ran `replot()` — concurrent `canvas.draw()` segfaults.
   *Fix*: In legacy mode, run visibility changes synchronously on the main thread.

2. **Rapid successive canvas.draw() bombardment**: During editor activation, the
   `deactivate()`→`activate()`→`edit_fcexcellon()` flow triggered ~12-15 intermediate
   `canvas.draw()` calls via `ShapeCollectionLegacy.clear/visible/enabled/redraw()` →
   `auto_adjust_axes()` → `adjust_axes()` → `canvas.draw()`. On macOS Qt5Agg backend,
   rapid successive renders can segfault.
   *Fix*: Added batch draw mode to `PlotCanvasLegacy` (`_batch_draw` flag) that suppresses
   intermediate `canvas.draw()` in `adjust_axes()`. `object2editor()` enables batch mode during
   editor setup and does a single `canvas.draw_idle()` at the end.

3. **Double-click signal connection leak + unguarded disconnect() calls**:
   `graph_event_connect('mouse_double_click', ...)` returned `None` (Qt signal.connect() returns
   None), so `graph_event_disconnect(None)` was a no-op — the handler was never disconnected,
   leaking connections on each editor enter/exit cycle. Additionally, signal `disconnect()` calls
   in `connect_canvas_event_handlers()` had no try/except, allowing TypeErrors to propagate into
   Qt's C++ event loop (segfault on macOS).
   *Fix*: `graph_event_connect()` now returns a sentinel tuple for Qt signals, and
   `graph_event_disconnect()` handles both matplotlib CIDs and Qt signal tuples.
   All `disconnect()` calls wrapped in try/except.

4. **`raise` in editor event handlers**: `on_exc_click_release()` had `raise` statements inside
   exception handlers that propagated exceptions back through matplotlib's event dispatch into
   Qt's event loop. Removed the `raise` statements.

5. **Worker thread race on properties tree widget**: `build_ui()` dispatches a worker thread
   (via `add_properties_items()` → `job_thread`) to calculate object dimensions. When done, it
   emits `calculations_finished` with a `dims` tree widget item. If the user enters an editor
   before the worker finishes, the properties UI is replaced, destroying the tree widget. When
   `update_area_chull()` receives the signal and tries `treeWidget.addChild(location, ...)`,
   it accesses a deleted Qt C++ object → segfault.
   *Fix*: Guard `update_area_chull()` with `call_source != 'app'` check (skip in editor mode),
   `sip.isdeleted()` checks on the tree widget and location item, and try/except wrapper.
   Also guard the signal emission in `job_thread` with the same `call_source` check.
