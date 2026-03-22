# Electric Plan

Electric Plan is an early-stage pygame application for sketching floor plans and growing into a lightweight electrical blueprint emulator.

## Current scope

This first setup focuses on the foundation for a floor-plan editor:

- pygame application bootstrap
- resizable window with a drawing surface
- pan and zoom camera controls
- background grid
- wall drawing tool
- object placement tool for an initial panel marker
- wall-aware panel placement that aligns panels to nearby wall rotation
- click-through panel editor view for breaker, bus, terminal, and wire layout experimentation
- floor-plan conduit drawing and panel-editor conduit handoff back into the plan
- side status panel with active tool and controls

## Controls

- `1`: Select tool
- `2`: Wall tool
- `3`: Panel tool
- `Left Click`: Use active tool
- `4`: Conduit tool
- `Right Click + Drag`: Pan camera
- `Mouse Wheel`: Zoom
- `Escape`: Cancel current wall preview
- `Delete` or `Backspace`: Delete selected item

Panels placed near a wall will snap onto that wall and inherit its rotation.
Click an existing panel in select mode to open the dedicated panel editor view, then press `Esc` or use the back button to return to the floor plan.
Inside the panel editor, use the tool palette and part menu for faster switching, easier wire routing, and sending conduit placement back to the floor plan.

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
   python main.py
   ```

## Project layout

```text
.
├── main.py
├── requirements.txt
└── src
    └── electric_plan
        ├── __init__.py
        ├── app.py
        ├── models.py
        ├── panel_editor.py
        └── settings.py
```
