#!/usr/bin/env python3
"""
Geo Monitor - Doubao Native Messaging Host.
Started by Chrome when the extension calls connectNative('com.geo_monitor_doubao').
Bridges between the extension and the Python adapter via file I/O.

Command file: ~/.geo-monitor/doubao_cmd.json
Result file:  ~/.geo-monitor/doubao_result.json
"""

import sys, json, struct, os, time
from pathlib import Path

CMD_DIR = Path.home() / '.geo-monitor'
CMD_FILE = CMD_DIR / 'doubao_cmd.json'
RESULT_FILE = CMD_DIR / 'doubao_result.json'


def read_message():
    """Read a native messaging message from stdin (4-byte length prefix + JSON)"""
    raw = sys.stdin.buffer.read(4)
    if not raw or len(raw) < 4:
        return None
    length = struct.unpack('<I', raw)[0]
    return json.loads(sys.stdin.buffer.read(length).decode())


def send_message(msg):
    """Send a native messaging message to stdout"""
    data = json.dumps(msg, ensure_ascii=False).encode()
    sys.stdout.buffer.write(struct.pack('<I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main():
    CMD_DIR.mkdir(parents=True, exist_ok=True)

    # Clear stale files
    CMD_FILE.unlink(missing_ok=True)
    RESULT_FILE.unlink(missing_ok=True)

    sys.stderr.write("[GM-DB Host] Ready, watching for commands\n")
    sys.stderr.flush()

    last_mtime = 0

    while True:
        # Check for incoming command from adapter (written to file)
        if CMD_FILE.exists():
            mtime = CMD_FILE.stat().st_mtime
            if mtime > last_mtime:
                last_mtime = mtime
                try:
                    with open(CMD_FILE, 'r', encoding='utf-8') as f:
                        cmd = json.load(f)

                    sys.stderr.write(f"[GM-DB Host] Command: {cmd.get('action')} q={cmd.get('question','')[:40]}\n")
                    sys.stderr.flush()

                    # Forward to extension
                    send_message(cmd)

                    # Wait for extension response
                    resp = read_message()
                    if resp:
                        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(resp, f, ensure_ascii=False, indent=2)
                        sys.stderr.write(f"[GM-DB Host] Result: success={resp.get('success')}\n")
                        sys.stderr.flush()

                    CMD_FILE.unlink(missing_ok=True)

                except Exception as e:
                    sys.stderr.write(f"[GM-DB Host] Error: {e}\n")
                    sys.stderr.flush()
                    # Write error result
                    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                        json.dump({"success": False, "error": str(e)}, f)
                    CMD_FILE.unlink(missing_ok=True)

        time.sleep(0.5)


if __name__ == '__main__':
    main()
