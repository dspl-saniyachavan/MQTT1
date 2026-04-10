import re

# ── Fix 1: dashboard/content.tsx ─────────────────────────────────────────────
path = '/home/saniyachavani/Documents/PrecisionpulseDocs/dspl-precision-pulse-frontend/src/app/dashboard/content.tsx'
content = open(path).read()

old = (
    "    if (connectionState === 'offline' && prev !== 'offline') {\n"
    "      showBanner('warn', '\u26a0 MQTT disconnected \u2014 data buffering locally');\n"
    "      // Keep last known data visible \u2014 do NOT clear history\n"
    "    }\n"
    "    if (connectionState === 'reconnecting') {\n"
    "      showBanner('info', '\u21bb Reconnecting to MQTT broker\u2026');\n"
    "    }\n"
    "    if (connectionState === 'online' && prev === 'reconnecting') {\n"
    "      showBanner('success', '\u2713 MQTT reconnected \u2014 streaming resumed');\n"
    "    }"
)

new = (
    "    if (connectionState === 'offline' && prev !== 'offline') {\n"
    "      showBanner('warn', '\u26a0 MQTT disconnected \u2014 data buffering locally');\n"
    "      // Clear history so chart shows \"Collecting data\u2026\" not frozen old values\n"
    "      _telemetryHistory = [];\n"
    "      _latestData = { timestamp: Date.now() };\n"
    "      _prevValues = {};\n"
    "      setTelemetryHistory([]);\n"
    "      setLatestData({ timestamp: Date.now() });\n"
    "      setPrevValues({});\n"
    "    }\n"
    "    if (connectionState === 'reconnecting') {\n"
    "      showBanner('info', '\u21bb Reconnecting to MQTT broker\u2026');\n"
    "    }\n"
    "    if (connectionState === 'online' && prev !== 'online') {\n"
    "      showBanner('success', '\u2713 MQTT reconnected \u2014 streaming resumed');\n"
    "    }"
)

if old in content:
    content = content.replace(old, new)
    open(path, 'w').write(content)
    print('dashboard/content.tsx patched OK')
else:
    print('ERROR: old block not found in content.tsx')
    # show lines 74-88
    for i, l in enumerate(content.split('\n')[73:88], 74):
        print(f'{i}: {repr(l)}')

# ── Fix 2: useMqttStatus.ts — don't flip to online from sync_status ──────────
path2 = '/home/saniyachavani/Documents/PrecisionpulseDocs/dspl-precision-pulse-frontend/src/hooks/useMqttStatus.ts'
c2 = open(path2).read()

old2 = (
    "      // If backend reports reconnected, ensure we show online\n"
    "      if (data.status === 'reconnected' || data.status === 'synced') {\n"
    "        setOnline();\n"
    "      }"
)
new2 = (
    "      // Do NOT flip to online from sync_status alone —\n"
    "      // only mqtt_status events from the desktop are authoritative."
)

if old2 in c2:
    c2 = c2.replace(old2, new2)
    open(path2, 'w').write(c2)
    print('useMqttStatus.ts patched OK')
else:
    print('ERROR: old block not found in useMqttStatus.ts')
    idx = c2.find('reconnected')
    print(repr(c2[max(0,idx-100):idx+200]))
