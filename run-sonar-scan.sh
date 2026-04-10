#!/usr/bin/env bash
# run-sonar-scan.sh — Install sonar-scanner (if needed) and scan all three projects
set -e

SONAR_URL="http://localhost:9000"
SCANNER_VERSION="6.2.1.4610"
SCANNER_DIR="$HOME/.sonar/sonar-scanner-${SCANNER_VERSION}-linux-x64"
SCANNER_BIN="$SCANNER_DIR/bin/sonar-scanner"
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Install sonar-scanner CLI if missing ───────────────────────────────────
if [ ! -f "$SCANNER_BIN" ]; then
  echo "[SETUP] Downloading sonar-scanner ${SCANNER_VERSION}..."
  mkdir -p "$HOME/.sonar"
  ZIP="$HOME/.sonar/sonar-scanner.zip"
  curl -sSL \
    "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-${SCANNER_VERSION}-linux-x64.zip" \
    -o "$ZIP"
  unzip -q "$ZIP" -d "$HOME/.sonar"
  rm "$ZIP"
  echo "[SETUP] sonar-scanner installed at $SCANNER_BIN"
fi

export PATH="$SCANNER_DIR/bin:$PATH"

# ── 2. Wait for SonarQube to be UP ───────────────────────────────────────────
echo "[WAIT] Waiting for SonarQube at $SONAR_URL ..."
for i in $(seq 1 30); do
  STATUS=$(curl -s "$SONAR_URL/api/system/status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  if [ "$STATUS" = "UP" ]; then echo "[WAIT] SonarQube is UP"; break; fi
  echo "[WAIT] Attempt $i: status=$STATUS — retrying in 10s..."
  sleep 10
done

if [ "$STATUS" != "UP" ]; then
  echo "[ERROR] SonarQube did not become ready. Start it first:"
  echo "  docker compose -f docker-compose.sonar.yml up -d"
  exit 1
fi

# ── 3. Helper: read token from sonar-project.properties ──────────────────────
get_token() {
  grep "^sonar.token=" "$1/sonar-project.properties" | cut -d= -f2
}

# ── 4. Scan backend ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo " Scanning: PrecisionPulse Backend"
echo "══════════════════════════════════════════"
cd "$ROOT/dspl-precision-pulse-backend"

# Generate coverage if pytest + pytest-cov available
if python3 -m pytest --version &>/dev/null && pip show pytest-cov &>/dev/null; then
  python3 -m pytest tests/ \
    --cov=app --cov=config \
    --cov-report=xml:coverage.xml \
    --junitxml=test-results.xml \
    -q 2>/dev/null || true
fi

sonar-scanner \
  -Dsonar.token="$(get_token .)" \
  -Dsonar.host.url="$SONAR_URL"

# ── 5. Scan desktop ───────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo " Scanning: PrecisionPulse Desktop"
echo "══════════════════════════════════════════"
cd "$ROOT/dspl-precision-pulse-desktop"

if python3 -m pytest --version &>/dev/null && pip show pytest-cov &>/dev/null; then
  python3 -m pytest tests/ \
    --cov=src \
    --cov-report=xml:coverage.xml \
    -q 2>/dev/null || true
fi

sonar-scanner \
  -Dsonar.token="$(get_token .)" \
  -Dsonar.host.url="$SONAR_URL"

# ── 6. Scan frontend ──────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo " Scanning: PrecisionPulse Frontend"
echo "══════════════════════════════════════════"
cd "$ROOT/dspl-precision-pulse-frontend"

# Generate lcov coverage if jest is available
if [ -f "node_modules/.bin/jest" ]; then
  npx jest --coverage --coverageReporters=lcov --passWithNoTests 2>/dev/null || true
fi

sonar-scanner \
  -Dsonar.token="$(get_token .)" \
  -Dsonar.host.url="$SONAR_URL"

echo ""
echo "✓ All scans complete. View results at: $SONAR_URL"
