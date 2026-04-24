#!/usr/bin/env python3
"""
ConXDocs RAG CLI — fallback script when MCP/VS Code extension is not available.

Usage:
  python query_rag.py --mode query     --question "How do I use core_ssh?"
  python query_rag.py --mode generate  --description "Test that reboots ECU1" [--type ssh|power|gnss|general]
  python query_rag.py --mode convert   --robot-file path/to/test.robot
  python query_rag.py --mode convert   --robot-content "*** Test Cases ***\n..."
  python query_rag.py --mode health

RAG server default: http://10.41.80.199:8504
Override with --server <url> or env var CONXDOCS_SERVER.
"""

import argparse
import json
import os
import sys
import urllib.request
from typing import Any, Dict, Optional
import urllib.error
import pathlib


DEFAULT_SERVER = os.environ.get("CONXDOCS_SERVER", "http://10.41.80.199:8504")
TIMEOUT = 60  # seconds


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] Server returned HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Could not reach server: {e.reason}", file=sys.stderr)
        print(f"  Is the RAG server running at {url}?", file=sys.stderr)
        print(f"  Try: curl {DEFAULT_SERVER}/health", file=sys.stderr)
        sys.exit(1)


def _get(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"[ERROR] Could not reach server: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def do_health(server: str) -> None:
    result = _get(f"{server}/health")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def do_query(server: str, question: str) -> None:
    result = _post(f"{server}/api/query", {"question": question})

    print("\n" + "=" * 60)
    print("SVAR:")
    print("=" * 60)
    print(result.get("answer", "(inget svar)"))

    sources = result.get("sources", [])
    if sources:
        print("\n--- Källor ---")
        for src in sources:
            title = src.get("title", "")
            url = src.get("url", "")
            print(f"  • {title}" + (f"  →  {url}" if url else ""))
    print()


def do_generate(server: str, description: str, test_type: str) -> None:
    # Auto-detect type from description if not provided
    if not test_type or test_type == "general":
        lower = description.lower()
        if "power" in lower or "sleep" in lower or "reboot" in lower:
            test_type = "power"
        elif "ssh" in lower:
            test_type = "ssh"
        elif "gnss" in lower or "gps" in lower or "satellite" in lower:
            test_type = "gnss"
        else:
            test_type = "general"

    result = _post(f"{server}/api/generate", {
        "description": description,
        "test_type": test_type,
    })

    checks = result.get("conxtfw_checks", {})
    valid = result.get("valid", False)
    code = result.get("code", "")

    print("\n" + "=" * 60)
    print(f"GENERERAD TEST  (typ: {test_type})")
    print("=" * 60)
    print(code)
    print()
    print("--- Validering ---")
    print("  Syntax:         " + ("✅ OK" if valid else f"⚠️  {result.get('syntax_error', 'fel')}"))
    print("  Markers:        " + ("✅" if checks.get("has_mandatory_markers") else "⚠️  SAKNAS — verifiera mot repots befintliga pytestmark-mönster (owner, test_scope, variant, project, type_designation, build_type)"))
    print("  AAA-mönster:    " + ("✅" if checks.get("follows_aaa_pattern") else "⚠️  Saknas Arrange/Act/Assert-struktur"))
    print("  Docstring:      " + ("✅" if checks.get("has_docstring") else "⚠️  Saknar docstring"))
    print("  Assertions:     " + ("✅" if checks.get("has_assertions") else "⚠️  Inga assertions"))
    print()

    if not valid or not checks.get("has_mandatory_markers"):
        print("[NOTERA] Koden innehåller varningar — granska före commit.", file=sys.stderr)


def do_convert(server: str, robot_content: str, filename: str = "Unknown", resource_files: Optional[Dict[str, str]] = None) -> None:
    payload: Dict[str, Any] = {
        "robot_content": robot_content,
        "filename": filename,
    }
    if resource_files:
        payload["resource_files"] = resource_files
    result = _post(f"{server}/api/convert", payload)

    meta = result.get("robot_metadata", {})
    code = result.get("code", "")
    valid = result.get("valid", False)

    print("\n" + "=" * 60)
    print("KONVERTERAT FRÅN ROBOT FRAMEWORK")
    print("=" * 60)

    test_cases = meta.get("test_cases", [])
    if test_cases:
        print(f"Ursprungliga testfall: {', '.join(test_cases)}\n")

    ecu_vars = meta.get("ecu_variables", {})
    if ecu_vars:
        print("ECU-variabler:")
        for k, v in ecu_vars.items():
            print(f"  {k} → {v}")
        print()

    print(code)
    print()
    print("--- Validering ---")
    print("  Syntax: " + ("✅ OK" if valid else f"⚠️  {result.get('syntax_error', 'fel')}"))
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ConXDocs RAG CLI — använd utan MCP/extension",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"RAG-server URL (standard: {DEFAULT_SERVER})",
    )
    parser.add_argument(
        "--mode",
        choices=["query", "generate", "convert", "health"],
        required=True,
        help="Vilket API-läge att använda",
    )

    # query
    parser.add_argument("--question", help="Fråga till dokumentations-RAG (mode=query)")

    # generate
    parser.add_argument("--description", help="Beskrivning av test att generera (mode=generate)")
    parser.add_argument(
        "--type",
        dest="test_type",
        default="general",
        choices=["power", "ssh", "gnss", "general"],
        help="Testtyp för generering",
    )

    # convert
    parser.add_argument("--robot-file", help="Sökväg till .robot-fil (mode=convert)")
    parser.add_argument("--robot-content", help="Robot Framework-innehåll som sträng (mode=convert)")
    parser.add_argument(
        "--resource-file",
        dest="resource_files",
        action="append",
        metavar="PATH",
        help="Sökväg till resurs-fil (.resource/.robot). Kan anges flera gånger.",
    )

    args = parser.parse_args()
    server = args.server.rstrip("/")

    if args.mode == "health":
        do_health(server)

    elif args.mode == "query":
        if not args.question:
            parser.error("--question krävs för mode=query")
        do_query(server, args.question)

    elif args.mode == "generate":
        if not args.description:
            parser.error("--description krävs för mode=generate")
        do_generate(server, args.description, args.test_type)

    elif args.mode == "convert":
        if args.robot_file:
            path = pathlib.Path(args.robot_file)
            if not path.exists():
                print(f"[ERROR] Filen hittades inte: {path}", file=sys.stderr)
                sys.exit(1)
            robot_content = path.read_text(encoding="utf-8")
            filename = path.name
        elif args.robot_content:
            robot_content = args.robot_content
            filename = "inline.robot"
        else:
            # Read from stdin if piped
            if not sys.stdin.isatty():
                robot_content = sys.stdin.read()
                filename = "stdin.robot"
            else:
                parser.error("--robot-file eller --robot-content krävs för mode=convert")

        # Load resource files
        resource_files = {}
        for res_path_str in (args.resource_files or []):
            res_path = pathlib.Path(res_path_str)
            if not res_path.exists():
                print(f"[ERROR] Resursfil hittades inte: {res_path}", file=sys.stderr)
                sys.exit(1)
            resource_files[res_path.name] = res_path.read_text(encoding="utf-8")
            print(f"[INFO] Läser resursfil: {res_path.name}")

        do_convert(server, robot_content, filename, resource_files if resource_files else None)


if __name__ == "__main__":
    main()
