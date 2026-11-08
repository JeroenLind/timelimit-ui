import sys

out = sys.argv[1]
W, H = 990, 760
els = []


def box(x, y, w, h, title, sub=None, cls="b"):
    t = f'<text x="{x + w / 2}" y="{y + (20 if sub else h / 2 + 5)}" class="t">{title}</text>'
    if sub:
        for i, line in enumerate(sub.split("|")):
            t += f'<text x="{x + w / 2}" y="{y + 38 + i * 15}" class="s">{line}</text>'
    els.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" class="{cls}"/>{t}'
    )


def band(x, y, w, h, label):
    els.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="band"/><text x="{x + 10}" y="{y + 16}" class="bl">{label}</text>'
    )


def arrow(d, dotted=False, label=None, lx=0, ly=0, anchor="start"):
    c = "ad" if dotted else "a"
    els.append(f'<path d="{d}" class="{c}" marker-end="url(#h)"/>')
    if label:
        els.append(
            f'<text x="{lx}" y="{ly}" class="lb" text-anchor="{anchor}">{label}</text>'
        )


# bands
band(200, 92, 730, 84, "1 · Entry (Flask)")
band(200, 196, 730, 84, "2 · Services (business logic)")
band(200, 296, 730, 144, "3 · Sync engine (background threads)")
band(200, 470, 730, 90, "4 · Gateways")

# domain bar
els.append('<rect x="30" y="196" width="140" height="244" rx="8" class="dom"/>')
els.append('<text x="100" y="222" class="t">Domain</text>')
for i, l in enumerate(
    [
        "pure, no I/O",
        "",
        "action_builder",
        "ids",
        "bitmask",
        "validation",
        "",
        "depends on",
        "nothing",
    ]
):
    els.append(f'<text x="100" y="{244 + i * 16}" class="s">{l}</text>')

box(330, 20, 470, 50, "Browser", "views · state · i18n · theme · api module")
box(220, 116, 300, 50, "Routes", "thin: parse, call service, error envelope", "b")
box(640, 116, 260, 50, "SSE hub", "live updates to the browser", "b")
box(
    220,
    220,
    300,
    50,
    "Rules · Category · Usage · ExtraTime",
    "Family · Settings · TestUser services",
    "b",
)
box(640, 220, 160, 50, "SyncService", "push, then pull", "b")
box(230, 336, 130, 58, "Socket listener", "server: should sync", "b")
box(372, 336, 130, 58, "Timers", "poll · health · restore", "b")
box(520, 336, 180, 58, "action_pusher", "sequence numbers,|integrity", "b")
box(730, 336, 170, 58, "Sync worker", "one thread, job queue", "b")
box(330, 494, 230, 52, "Server client", "the only HTTP to the server", "g")
box(640, 494, 260, 52, "Repository", "the only SQL", "g")
box(330, 600, 230, 46, "TimeLimit server", "official, unmodified", "x")
box(640, 600, 260, 46, "SQLite cache", "data/ folder", "x")

# arrows
arrow("M370 70 V116", label="HTTP JSON", lx=378, ly=86)
arrow("M700 116 V70", dotted=True, label="events (SSE)", lx=708, ly=86)
arrow("M370 166 V220")
arrow("M520 245 H640")
arrow("M800 270 V336", label="enqueue job", lx=808, ly=306)
# bus: socket + poller -> worker
els.append('<path d="M295 336 V318 H760 V336" class="a" marker-end="url(#h)"/>')
els.append('<path d="M437 336 V318" class="a"/>')
arrow("M730 365 H700")
arrow("M885 336 V166", dotted=True, label="cache changed", lx=893, ly=189)
# to domain
arrow("M200 245 H170")
arrow("M200 390 H170")
# services -> repository (right corridor)
arrow("M930 250 H952 V520 H900")
els.append(
    '<text x="958" y="380" class="lb" transform="rotate(90 958 380)" text-anchor="middle">reads the cache</text>'
)
# sync engine -> gateways
arrow("M445 440 V494", label="push / pull", lx=453, ly=459)
arrow("M770 440 V494", label="store", lx=778, ly=459)
# gateways -> outside
arrow("M445 546 V600", label="REST", lx=453, ly=578)
arrow("M770 546 V600")
# websocket back
arrow(
    "M330 623 H295 V394", dotted=True, label="WebSocket", lx=287, ly=585, anchor="end"
)

# legend
lx = 30
ly = 690
els.append(
    f'<path d="M{lx} {ly} H{lx + 40}" class="a" marker-end="url(#h)"/><text x="{lx + 50}" y="{ly + 4}" class="lb">allowed call (downwards only)</text>'
)
els.append(
    f'<path d="M{lx + 260} {ly} H{lx + 300}" class="ad" marker-end="url(#h)"/><text x="{lx + 310}" y="{ly + 4}" class="lb">notification / event (never a call into a lower layer)</text>'
)
els.append(
    f'<text x="{lx}" y="{ly + 30}" class="lb">Rule: calls go downwards only. Routes never touch SQL or the server. Services reach SQL only through the Repository and never</text>'
)
els.append(
    f'<text x="{lx}" y="{ly + 46}" class="lb">talk to the server; only the Sync engine does, through the Server client. The Domain is pure and depends on nothing.</text>'
)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">
<defs><marker id="h" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#37474f"/></marker></defs>
<style>
.t{{font-size:13px;font-weight:600;text-anchor:middle;fill:#1b1b1b}}
.s{{font-size:11px;text-anchor:middle;fill:#455a64}}
.bl{{font-size:11px;font-weight:600;fill:#5d4037}}
.lb{{font-size:11px;fill:#37474f}}
.b{{fill:#ede7f6;stroke:#7e57c2;stroke-width:1.2}}
.g{{fill:#e3f2fd;stroke:#1565c0;stroke-width:1.5}}
.x{{fill:#fff3e0;stroke:#ef6c00;stroke-width:1.5}}
.dom{{fill:#e8f5e9;stroke:#2e7d32;stroke-width:1.5}}
.band{{fill:#fffde7;stroke:#c9b458;stroke-width:1}}
.a{{fill:none;stroke:#37474f;stroke-width:1.5}}
.ad{{fill:none;stroke:#37474f;stroke-width:1.5;stroke-dasharray:5 4}}
</style>
<rect width="{W}" height="{H}" fill="#ffffff"/>
{chr(10).join(els)}
</svg>'''
open(out, "w", encoding="utf-8").write(svg)
