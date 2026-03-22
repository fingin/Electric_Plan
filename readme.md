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
- side status panel with active tool and controls

## Controls

- `1`: Select tool
- `2`: Wall tool
- `3`: Panel tool
- `Left Click`: Use active tool
- `Right Click + Drag`: Pan camera
- `Mouse Wheel`: Zoom
- `Escape`: Cancel current wall preview
- `Delete` or `Backspace`: Delete selected item

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
        └── settings.py
```
