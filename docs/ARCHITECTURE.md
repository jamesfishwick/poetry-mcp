# Architecture: Tools & Server

How the MCP tool layer is structured, the conventions that keep it working, and how to add a tool. Read this before touching `server.py` or `tools/`.

## Layers

```
MCP client
   │  calls a tool by name
   ▼
server.py            @mcp.tool wrappers (thin) + main() + catalog getters
   │  delegates to the plain impl
   ▼
tools/*_tools.py     impl functions (the actual logic; no @mcp.tool)
   │  uses
   ▼
catalog/ parsers/ writers/ models/    domain layer
```

`server.py` holds only:

- the `mcp = FastMCP(...)` instance and every `@mcp.tool()` wrapper,
- the four cached catalog getters — `get_catalog`, `get_submission_catalog`, `get_venue_catalog`, `get_nexus_manager` — plus their module globals,
- `main()` and the startup sequence.

Each wrapper is a few lines: keep the docstring/signature (that is the tool's MCP schema) and delegate to an impl in `tools/`. Example:

```python
@mcp.tool()
async def sync_catalog(force_rescan: bool = False) -> SyncResult:
    """..."""  # docstring is the MCP schema — keep it here
    return await sync_catalog_impl(force_rescan, catalog=get_catalog())
```

## Two dependency-injection patterns

Impl functions never import `server` (that would be a circular import). They get their dependencies one of two ways:

1. **Threaded parameters** — `catalog_tools`, `quality_tools`, `submission_tools`, `venue_tools`, `nexus_tools`. The impl takes the catalog(s)/registry as **keyword-only** args; the wrapper supplies them:

   ```python
   async def get_venue_impl(venue_name: str, *, ven_cat, sub_cat): ...
   # wrapper: return await get_venue_impl(name, ven_cat=get_venue_catalog(), sub_cat=get_submission_catalog())
   ```

   Prefer this pattern — it is stateless and trivially testable.

2. **initialize + module global** — `enrichment_tools`, `chain_tools`, `similarity_tools`. `initialize_*_tools(catalog, ...)` stashes the catalog in a module global that the impls read via a `_get_catalog()`-style accessor that raises if uninitialized. `main()` calls every `initialize_*_tools(cat)` at startup (and nexus create/delete re-run them to refresh the registry).

Both keep `server.py` thin and the impls import-cycle-free.

## Conventions (these prevent real bugs we have hit)

- **Never call one `@mcp.tool` from another.** `@mcp.tool()` returns a non-callable `FunctionTool`; `other_tool()` raises `TypeError`, and `other_tool.fn()` is a fragile workaround. Call the **plain impl** instead (e.g. `await _get_all_nexuses()`, the enrichment impl). There should be **zero `.fn()` calls** in `server.py`.
- **Don't swallow errors into success.** A catch-all that returns `success=True` (or logs-and-continues) hides real failures. Narrow the `except` to expected types, chain with `raise ... from e`, and surface partial failures in the result (see `delete_nexus`'s `cleanup_errors`). Startup fails loud if the catalog can't load.
- **Sanitize data-derived filenames.** Anything from frontmatter used to build a write path goes through `utils.slugify_filename` first (prevents path traversal). See the venue write sites.
- **Keep tests config-hermetic and patch the right module.** `patch` where a name is _used_, not where it is defined: an impl in `submission_tools` uses `submission_tools.load_config`, so patch that — patching `server.load_config` won't intercept it. Tests must pass with no `~/.config/poetry-mcp/config.yaml` (CI runs config-less); verify locally with `env HOME=/tmp/none POETRY_MCP_CONFIG= uv run pytest`.

## Adding a tool

1. Write the impl in the relevant `tools/*_tools.py` (or a new module), taking dependencies as keyword-only params or via an `initialize_*` global.
2. Add a thin `@mcp.tool()` wrapper in `server.py` with the user-facing docstring/signature that delegates to the impl.
3. If the module is new and uses the initialize pattern, call its `initialize_*_tools(cat)` at each startup point in `main()`.
4. Test the impl directly (pass a fake catalog / mock the module's own `load_config`), and confirm the tool still registers: `python -c "import poetry_mcp.server as s; from fastmcp.tools import FunctionTool; print(sum(isinstance(getattr(s,n),FunctionTool) for n in dir(s)))"`.

## Tooling

- Single toolchain: **ruff** (format + lint). Config in `pyproject.toml` (`[tool.ruff.lint]` selects E/F/W/I/UP/B). Run `make format` / `make lint` / `make test`, or `make check` to mirror CI.
- **CI** (`.github/workflows/ci.yml`) runs ruff check, `ruff format --check`, mypy (advisory), and pytest on Python **3.10 and 3.12** for every PR. 3.10 is the floor and catches version-specific issues.
