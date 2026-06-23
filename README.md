# ETABS MCP Server

A Model Context Protocol (MCP) server that connects Large Language Models (LLMs) to CSI ETABS, a premier structural engineering software.

This server enables AI assistants (like Claude, Cursor, etc.) to:

- Create, open, and save ETABS models
- Define materials, sections, and structural geometry
- Apply loads and assign properties
- Run structural analysis and design checks
- Extract analysis results and design summaries
- Query and modify ETABS database tables

It uses the `comtypes` library in Python to interact directly with the ETABSv1 COM API, providing a seamless bridge between modern AI and legacy Windows COM applications.

## Prerequisites

- **Windows OS** (required for COM integration — `comtypes` does not work on macOS/Linux)
- **CSI ETABS** installed and licensed (v19, v20, v21, or v22)
- **Python 3.10+**
- **uv** (recommended) or **pip**

## Repository Layout

```
ETABS-mcp/
├── pyproject.toml                # build config & entry point
├── README.md
├── etabs_mcp_config.json         # runtime config (units, auto-connect, …)
├── src/
│   └── etabs_mcp/
│       ├── __init__.py
│       ├── server.py             # FastMCP entry point  (run via `etabs-mcp`)
│       ├── etabs_connection.py   # COM singleton manager
│       ├── helpers.py            # shared utils, units, response formatting
│       └── tools/
│           ├── __init__.py
│           ├── analysis.py
│           ├── assignments.py
│           ├── database_tables.py
│           ├── design.py
│           ├── generic_api.py
│           ├── loads.py
│           ├── model_control.py
│           ├── model_geometry.py
│           ├── properties.py
│           ├── results.py
│           ├── seismic.py                 # IS 1893 modal + RSA + drift
│           ├── selection.py
│           ├── stiffness_modifiers.py     # ACI 318 + IS 456 cracked-section presets
│           └── stories_grids.py
```

## Installation

1. Clone the repo and install the package in editable mode:

   ```bash
   git clone https://github.com/mdvaleed7/ETABS-mcp.git
   cd ETABS-mcp
   pip install -e .
   ```

   Or with `uv`:

   ```bash
   uv pip install -e .
   ```

2. Verify the entry point is registered:

   ```bash
   etabs-mcp --help
   ```

   (The server itself only starts speaking MCP over stdio, so don't expect
   pretty output — just confirm the command exists.)

## Configuration for MCP Clients

### Claude Desktop

Add this to your `claude_desktop_config.json` (usually at
`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "etabs": {
      "command": "etabs-mcp",
      "args": []
    }
  }
}
```

If `etabs-mcp` is not on your PATH, use the full path to the script, e.g.:

```json
{
  "mcpServers": {
    "etabs": {
      "command": "python",
      "args": ["-m", "etabs_mcp.server"]
    }
  }
}
```

Make sure you run this Python from the same virtual environment where you
installed the package.

### Cursor

In Cursor settings → Features → MCP, add a new server:

- **Type:** `command`
- **Name:** `ETABS`
- **Command:** `etabs-mcp` (or the full path to your venv's script)

### Claude Code / other stdio MCP clients

```bash
claude mcp add etabs -- etabs-mcp
```

## Tool Categories

The server exposes **69 tools** grouped by domain:

| Category | Tools | Key functions |
|---|---|---|
| **Model Control** | 6 | `etabs_get_status`, `etabs_new_model`, `etabs_open_model`, `etabs_save_model`, `etabs_close_model`, `etabs_set_units` |
| **Geometry** | 7 | `etabs_add_point`, `etabs_add_frame`, `etabs_add_area`, `etabs_get_all_*`, `etabs_delete_object` |
| **Stories & Grids** | 4 | story/grid definition and retrieval |
| **Properties** | 7 | materials, frame sections (I, tube, concrete), area sections, rebar |
| **Assignments** | 6 | frame section, releases, area section, diaphragm, pier/spandrel labels |
| **Stiffness Modifiers** | 3 | ACI 318-19 + **IS 456:2000** cracked-section presets for beams/columns/walls/slabs |
| **Loads** | 7 | patterns, cases (Linear/Modal/RSA/Nonlinear), combinations, point/frame/area loads |
| **Analysis** | 4 | run solver, case status, active DOF, delete results |
| **Results** | 5 | displacements, frame forces, reactions, base reactions |
| **🆕 Seismic** | **7** | **IS 1893:2016 modal + RSA + drift check** (see below) |
| **Design** | 4 | steel & concrete design, code setting, summary results |
| **Database Tables** | 4 | full interactive access to ETABS tables |
| **Selection** | 4 | select objects, groups, named selections |
| **Generic API** | 1 | `etabs_call_api` — escape hatch for all 1,300+ ETABS methods |

---

### 🆕 Seismic Module — IS 1893:2016 / ASCE 7 / EC8

The new `seismic.py` module adds 7 tools for complete response spectrum workflow:

| Tool | Purpose |
|---|---|
| `etabs_define_modal_case` | Eigenvector/Ritz case; max modes, shift value |
| `etabs_define_response_spectrum` | RSA case — CQC/SRSS, eccentricity, scale factors |
| `etabs_get_modal_results` | Periods, frequencies, mass participation; auto-checks IS 1893 Cl. 7.7.5a 90% mass rule |
| `etabs_get_story_drifts` | Inter-storey drift ratios with IS 1893 Cl. 7.11.1 h/250 check |
| `etabs_get_story_forces` | Storey shear and overturning moments per floor |
| `etabs_set_is1893_seismic_params` | Computes ETABS scale factor from Zone/I/R/soil; step-by-step workflow guide |
| `etabs_check_is1893_drift` | Full X+Y direction drift compliance report with PASS/FAIL per storey |

**IS 1893:2016 RSA workflow (6 steps):**
```
1. etabs_set_is1893_seismic_params(zone="III", I=1.2, R=5.0) → get scale factor
2. Define IS 1893 spectrum function in ETABS (manually or via etabs_call_api)
3. etabs_define_modal_case("MODAL", max_modes=36)
4. etabs_run_analysis()
5. etabs_get_modal_results("MODAL") → verify ≥ 90% mass (Cl. 7.7.5a)
6. etabs_define_response_spectrum("EQX", scale_x=SF) + "EQY"
7. etabs_check_is1893_drift("EQX", "EQY") → PASS/FAIL report
```

### Stiffness Modifiers (ACI 318 presets)

The server ships with baked-in ACI 318-19 Table 6.6.3.1.1(a) cracked-section
factors, so an LLM can apply them to a whole model in one tool call.

**One-shot for all four categories** — call `etabs_apply_aci_stiffness_modifiers`
with either explicit names or named ETABS groups per category:

```jsonc
// Apply ACI defaults to all members via groups
{
  "beam_group":   "BEAMS",
  "column_group": "COLUMNS",
  "wall_group":   "WALLS",
  "slab_group":   "SLABS"
}
```

Defaults applied:

| Category | Preset | Modifiers |
|---|---|---|
| Beams    | `aci_beam`    | I = 0.35 Ig, torsion = 0.20 |
| Columns  | `aci_column`  | I = 0.70 Ig, A = 0.70 Ag |
| Walls    | `aci_wall`    | I = 0.70 Ig, A = 0.70 Ag (uncracked) |
| Slabs    | `aci_slab`    | I = 0.25 Ig |

**Granular tools** for finer control:

- `etabs_assign_frame_stiffness_modifiers` — apply to specific frames with any
  of the presets `aci_beam`, `aci_beam_conservative`, `aci_column`,
  `aci_column_conservative`, `aci_spandrel`, `aisc_beam`, `is456_beam`,
  `is456_column`, `is456_beam_seismic`, `is456_shear_wall` — or pass individual
  `area / m2 / m3 / torsion / mass / weight` values to override.
- `etabs_assign_area_stiffness_modifiers` — apply to specific areas with any of
  the presets `aci_wall`, `aci_wall_cracked`, `aci_slab`, `aci_slab_joist`,
  `aci_drop_panel`, `steel_deck`, `is456_wall`, `is456_wall_cracked`,
  `is456_slab`, `is456_flat_slab`, `is456_ribbed_slab` — or override individual
  `f11 / f22 / f12 / m11 / m22 / m12 / v13 / v23` values.

> **Note on modifier ordering.** Frame modifiers are passed to ETABS as
> `[Area, M2, M3, Torsion, M2_weight, M3_weight, Mass, Weight]` and area
> modifiers as `[F11, F22, F12, M11, M22, M12, V13, V23]`. The Python tool
> exposes them as named parameters so you never transpose them by accident.
> If your ETABS version uses a different ordering, use `etabs_call_api` with
> `interface_path="FrameObj"` and `method_name="SetModifiers"` to pass the
> raw array directly.

## Architecture

This uses the [FastMCP](https://github.com/jlowin/fastmcp) framework.
Communication with the LLM happens over **stdio** while communication with
ETABS happens via **Windows COM** (using `comtypes`).

The server attempts to automatically attach to a running instance of ETABS
when started. If it cannot, the LLM can trigger `etabs_new_model` to launch a
fresh instance in the background.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'etabs_mcp'` | Run `pip install -e .` from the repo root (where `pyproject.toml` lives). |
| `comtypes` import error on macOS/Linux | This is expected — the server only runs on Windows. |
| ETABS won't auto-attach | Start ETABS manually, then call `etabs_get_status`. |
| `ConnectionError: Cannot launch ETABS` | Set `etabs_executable_path` in `etabs_mcp_config.json` to the full path of `ETABS.exe`. |

## License

MIT
