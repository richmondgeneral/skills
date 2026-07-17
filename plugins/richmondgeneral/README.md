# richmondgeneral plugin

Richmond General's full skill set as a single Claude plugin. Skills live under
`skills/<skill>/`. See the repository root `README.md` for the marketplace
install/update flow.

## Python environment

Skills that need Python run in the `uv` environment defined by `pyproject.toml`
+ `uv.lock` in this directory (the plugin root), so the plugin is self-contained
when installed from a marketplace. Scripts resolve it via `${CLAUDE_PLUGIN_ROOT}`
(set when a skill runs) or by walking up to this `pyproject.toml`
(e.g. `daily-briefing/scripts/run_briefing.sh`).

Dependencies: `requests`, `pymongo`, `qrcode[pil]`, `pillow`,
`google-generativeai`, `squareup` (dev: `pytest`, `ruff`).
