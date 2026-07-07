#!/usr/bin/env python3
"""
Geo Monitor - Doubao CLI Bridge.
Called by the Doubao adapter. Writes a geo_query command to the command file,
polls for the result, and prints JSON to stdout.

Usage: python3 doubao_cli.py '{"action":"geo_query","question":"..."}'
"""

import sys, json, time
from pathlib import Path

CMD_DIR = Path.home() / '.geo-monitor'
CMD_FILE = CMD_DIR / 'doubao_cmd.json'
RESULT_FILE = CMD_DIR / 'doubao_result.json'
TIMEOUT = 180  # seconds (Doubao is slow)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "Usage: doubao_cli.py '<json_command>'"}))
        sys.exit(1)

    try:
        cmd = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    CMD_DIR.mkdir(parents=True, exist_ok=True)

    # Clear any stale result
    RESULT_FILE.unlink(missing_ok=True)

    # Write command
    with open(CMD_FILE, 'w', encoding='utf-8') as f:
        json.dump(cmd, f, ensure_ascii=False)

    # Poll for result
    start = time.time()
    while time.time() - start < TIMEOUT:
        if RESULT_FILE.exists():
            try:
                with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                RESULT_FILE.unlink(missing_ok=True)
                print(json.dumps(result, ensure_ascii=False))
                return
            except Exception as e:
                print(json.dumps({"success": False, "error": f"Result read error: {e}"}))
                sys.exit(1)

        time.sleep(0.5)

    print(json.dumps({"success": False, "error": f"Timeout after {TIMEOUT}s"}))


if __name__ == '__main__':
    main()
