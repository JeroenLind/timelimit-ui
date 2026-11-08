#!/usr/bin/env python3
"""Compare the action wire formats of an Android client with the server reference.

Usage: compare_android_actions.py <android>/app/src/main/java/io/timelimit/android/sync/actions/Actions.kt actions-reference.md
Reads files only. Reports: types only on one side, outer-type mismatches (ParentAction/ChildAction/AppLogicAction
vs parent/child/appLogic) and top-level field-name differences. Known limit: PING is written with a literal
type string and is not detected from the client side (checked by hand)."""

import re, sys, pathlib, json

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
ref = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")

# --- android: split into top-level class chunks
starts = [
    (m.start(), m.group(1), m.group(0))
    for m in re.finditer(r"^(?:data class|class|object)\s+(\w+)", src, re.M)
]
starts = [
    (s, re.match(r"(?:data class|class|object)\s+(\w+)", src[s:]).group(1))
    for s, _ in [(a, b) for a, b, _ in starts]
]
android = {}
for i, (s, name) in enumerate(starts):
    e = starts[i + 1][0] if i + 1 < len(starts) else len(src)
    chunk = src[s:e]
    m = re.search(r'const val TYPE_VALUE = "([A-Z0-9_]+)"', chunk)
    if not m:
        continue
    consts = dict(re.findall(r'const val (\w+) = "([^"]*)"', chunk))
    ser = re.search(
        r"fun serialize\(writer: JsonWriter\)\s*\{(.*?)\n    \}", chunk, re.S
    )
    body = ser.group(1) if ser else ""
    fields = []
    for fm in re.finditer(r'writer\.name\((\w+|"[^"]+")\)', body):
        tok = fm.group(1)
        n = tok.strip('"') if tok.startswith('"') else consts.get(tok, tok)
        if n not in ("type", "TYPE") and n not in fields:
            fields.append(n)
    base = re.search(
        r"\)\s*:\s*(ParentAction|ChildAction|AppLogicAction)\(\)", chunk
    ) or re.search(r":\s*(ParentAction|ChildAction|AppLogicAction)\(\)", chunk[:600])
    android[m.group(1)] = (name, base.group(1) if base else "?", fields)

# --- server reference
server = {}
outer = None
cur = None
for line in ref.split("\n"):
    mo = re.match(r"## Outer type `(\w+)`", line)
    if mo:
        outer = mo.group(1)
        continue
    mt = re.match(r"### `([A-Z0-9_]+)`$", line)
    if mt and outer:
        cur = mt.group(1)
        server[cur] = (outer, [], [])
        continue
    if line.startswith("## "):
        cur = None
    mf = re.match(r"\| `(\w+)` \| .* \| (yes|no) \|", line)
    if mf and cur and cur in server:
        server[cur][1].append(mf.group(1))
        if mf.group(2) == "yes":
            server[cur][2].append(mf.group(1))

print(f"android types: {len(android)}  server types: {len(server)}")
print("\n== only on server (client never sends):")
for t in sorted(set(server) - set(android)):
    print("  ", t, server[t][0])
print("\n== only in android (server has no such type):")
for t in sorted(set(android) - set(server)):
    print("  ", t, android[t][:2])
print("\n== outer-type mismatches (android base class vs server outer type):")
bmap = {"ParentAction": "parent", "ChildAction": "child", "AppLogicAction": "appLogic"}
for t in sorted(set(android) & set(server)):
    if bmap.get(android[t][1]) != server[t][0]:
        print("  ", t, "android:", android[t][1], "server:", server[t][0])
print("\n== field mismatches:")
n = 0
for t in sorted(set(android) & set(server)):
    af = set(android[t][2])
    sf = set(server[t][1])
    req = set(server[t][2])
    extra = af - sf
    missing = req - af
    if extra or missing:
        n += 1
        print(
            f"  {t}: android sends extra {sorted(extra)}; required but not sent {sorted(missing)}"
        )
print("  (none)" if n == 0 else f"  {n} types with differences")
