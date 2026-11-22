"""Runs the eval cases against Claude models using the real MCP server and the fake library.

This script only RECORDS what happened. Scoring is done separately.
Usage (from the library-mcp folder):
    uv run python eval/run_eval.py --models sonnet --cases c01,c08
    uv run python eval/run_eval.py                      # all three models, all cases
"""
import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_store  # noqa: E402  (sets fake credentials, imports the real server)

import anthropic  # noqa: E402
from mcp.client import Client  # noqa: E402
from mcp.types import ElicitResult  # noqa: E402
import logging  # noqa: E402
logging.getLogger().setLevel(logging.WARNING)

MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
SYSTEM = "You are a helpful assistant. You can use tools to work with the user's saved reading library."
MAX_TURNS = 8
MAX_TOKENS = 8000
CASES_FILE = Path(__file__).parent / "cases.json"
RESULTS_DIR = Path(__file__).parent / "results"
FATAL_MARKERS = ("credit balance", "authentication", "invalid x-api-key", "permission")


def schema_of(tool):
    return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema")


def is_error(result):
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


async def run_case(api, model_id, case):
    library = fake_store.use_fake_library()  # fresh fake library for every case
    approval = case.get("approval", "decline")  # the simulated human; declines unless told otherwise
    prompts = []

    async def human(context, params):
        prompts.append(params.message)
        if approval == "accept":
            return ElicitResult(action="accept", content={"ok": True})
        return ElicitResult(action="decline")

    record = {
        "case": case["id"], "model": model_id, "tool_calls": [], "final_text": "",
        "turns": 0, "input_tokens": 0, "output_tokens": 0,
        "stop_reason": None, "error": None, "fatal": False,
    }
    started = time.perf_counter()
    try:
        async with Client(fake_store.server.mcp, elicitation_callback=human) as client:
            listing = await client.list_tools()
            tools = [
                {"name": t.name, "description": t.description or "", "input_schema": schema_of(t)}
                for t in listing.tools
            ]
            messages = [{"role": "user", "content": case["prompt"]}]
            for _ in range(MAX_TURNS):
                response = await api.messages.create(
                    model=model_id, max_tokens=MAX_TOKENS, system=SYSTEM,
                    tools=tools, messages=messages,
                )
                record["turns"] += 1
                record["input_tokens"] += response.usage.input_tokens
                record["output_tokens"] += response.usage.output_tokens
                record["stop_reason"] = response.stop_reason
                if response.stop_reason != "tool_use":
                    record["final_text"] = "\n".join(b.text for b in response.content if b.type == "text")
                    break
                # Send the whole assistant turn back, including any thinking blocks, unmodified.
                messages.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    try:
                        result = await client.call_tool(block.name, block.input)
                        text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                        err = is_error(result)
                    except Exception as exc:  # the model sees tool failures, like a real client would
                        text, err = f"Tool call failed: {exc}", True
                    record["tool_calls"].append(
                        {"name": block.name, "input": block.input, "is_error": err, "result": text[:1500]}
                    )
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": err}
                    )
                messages.append({"role": "user", "content": results})
            else:
                record["error"] = f"no final answer after {MAX_TURNS} turns"
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
        record["fatal"] = any(m in str(exc).lower() for m in FATAL_MARKERS)

    record["elapsed_s"] = round(time.perf_counter() - started, 2)
    record["inserted"] = list(library.inserted)
    record["approval_prompts"] = prompts
    return record


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="haiku,sonnet,opus")
    parser.add_argument("--cases", default="")
    args = parser.parse_args()

    cases = json.loads(CASES_FILE.read_text())["cases"]
    if args.cases:
        wanted = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    api = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from the environment
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for name in args.models.split(","):
        records = []
        for case in cases:
            rec = await run_case(api, MODELS[name], case)
            records.append(rec)
            used = ", ".join(c["name"] for c in rec["tool_calls"]) or "(none)"
            line = f"{name:7} {case['id']}  {rec['elapsed_s']:6.1f}s  tools: {used}"
            print(line + (f"   ERROR: {rec['error']}" if rec["error"] else ""))
            if rec["fatal"]:
                sys.exit("Stopping: this looks like a key or billing problem, not a one-off failure.")
        (RESULTS_DIR / f"{stamp}_{name}.json").write_text(json.dumps(records, indent=2))


asyncio.run(main())