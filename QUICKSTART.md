# Quickstart

Goal: a first working tool call in a few minutes, **with no accounts or API keys**. Demo mode runs the real server on a built-in sample library.

## What you need

- macOS or Linux, with `git`
- [`uv`](https://docs.astral.sh/uv/) (installs Python and dependencies for you):
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Try it in demo mode

1. Clone and enter the project:

   ```
   git clone <this repo's URL>
   cd library-mcp
   ```

2. Install everything:

   ```
   uv sync
   ```

3. Start the server under the MCP Inspector (a browser test console):

   ```
   uv run mcp dev eval/dev_server.py
   ```

   Open the URL it prints and click **Connect**.

4. Go to **Tools** and try, in this order:
   - `list_by_theme` with no arguments: the sample themes with counts
   - `search_links` with query `nash`: one result, with an `id`
   - `get_summary` with that `id`: three bullets and a quote
   - `add_link` with `https://example.org/great-article`: the Inspector shows an approval form with the exact cleaned URL. Nothing is saved until you tick the box and submit. In demo mode a saved link lives in memory only.

Tip: the Inspector's default request timeout is 10 seconds and keeps running while you read the approval form. If the call times out, raise the timeout in the Inspector's connection settings.

## Use it with your own library

The real server reads the same `links` table as the Sunday Digest project. It uses these columns: `id`, `url`, `created_at`, `summary`, `status`, `source`, `raw_message`.

1. Copy `.env.example` to `.env` and fill in your Supabase project URL and a **dedicated secret key** (create one key per component, so you can revoke it alone).
2. Run `uv run mcp dev server.py`.

## Connect Claude Desktop (local, read tools)

Add this to `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`), using **absolute** paths. Find the one for `uv` with `which uv`:

```json
{
  "mcpServers": {
    "library": {
      "command": "/ABSOLUTE/PATH/TO/uv",
      "args": ["run", "--project", "/ABSOLUTE/PATH/TO/library-mcp",
               "mcp", "run", "/ABSOLUTE/PATH/TO/library-mcp/server.py"]
    }
  }
}
```

Quit Claude Desktop fully (Cmd+Q) and reopen it. If the server doesn't work, read `~/Library/Logs/Claude/mcp-server-library.log`.

Claude Desktop did not show the approval form for `add_link` in my testing, so the save fails safely and nothing is written. Use the Inspector, or a client that supports MCP elicitation, to save links.

## Run the tests and the eval

```
uv run pytest -q                            # unit and safety tests, no network
uv run python eval/smoke_test.py            # fake library works through the real server
uv run python eval/run_eval.py              # needs ANTHROPIC_API_KEY; costs roughly $0.40
uv run python eval/score_eval.py            # scores the saved results
```