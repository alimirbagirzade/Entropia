#!/usr/bin/env bash
# Install Chromium for the Playwright jobs in e2e.yml, WITHOUT waiting on the
# Ubuntu font mirror.
#
# WHY — measured across three CI runs on 2026-08-19, not guessed.
#
# `playwright install --with-deps chromium` asks apt for ~30 packages. On the
# GitHub runner image every launch-critical library is ALREADY INSTALLED —
# libnss3, libatk*, libgbm1, libxkbcommon0, libdrm2, libcairo2, libpango,
# libcups2t64, xvfb, libfontconfig1 all report "is already the newest version".
# The only packages actually fetched are NINE FONT packages totalling 21.1 MB,
# and azure.archive.ubuntu.com was serving them at 9-17 kB/s:
#
#   PR #780, A11Y job:  "Fetched 21.1 MB in 38min 17s (9178 B/s)"
#                        -> 40-minute job budget gone; the suite got 15 seconds
#                           and was killed mid-first-test.
#
# In the very same job, Chromium itself — 173.8 MiB from Playwright's own CDN —
# downloaded in about FIVE SECONDS. The browser was never the problem. The
# fonts were, and fonts are not what makes Chromium launch.
#
# WHAT THIS CHANGES, AND THE RISK IT ACCEPTS (signed off by the maintainer,
# 2026-08-19). e2e.yml's acceptance-flows note warned that dropping
# `--with-deps` leaves Chromium unable to LAUNCH on missing shared libraries,
# which the harness books as a SKIP rather than a failure. That warning is
# about the LIBRARIES, and it stays honoured: the libraries are still installed
# here, taken from Playwright's own dependency list so they track the Playwright
# version instead of a list that rots. Only `fonts-*` / `xfonts-*` are dropped.
#
# The warning is also DEFUSED rather than argued away: this script ends by
# actually launching Chromium. If the surviving package set is ever
# insufficient, the job fails HERE, loudly, at install time — it can no longer
# degrade into a quiet SKIP further down the run.
#
# Known and accepted: glyphs for CJK, Thai and Cyrillic text fall back to the
# default font. Any visual-regression baseline that renders such text would
# show a diff — which is a visible failure, not a silent one.
set -uo pipefail

ATTEMPT_SECONDS="${PLAYWRIGHT_INSTALL_TIMEOUT_SECONDS:-420}"

log_warn() { echo "::warning::$*" >&2; }
log_err()  { echo "::error::$*" >&2; }

# ---------------------------------------------------------------- apt hygiene
# apt has no overall deadline of its own: a socket that opens but never
# delivers is waited on forever. These bound a DEAD connection. They cannot
# bound a SLOW one — that is what dropping the fonts is for.
if command -v sudo >/dev/null 2>&1; then
  sudo tee /etc/apt/apt.conf.d/99-entropia-ci-timeouts >/dev/null <<'APTEOF'
Acquire::http::Timeout "20";
Acquire::https::Timeout "20";
Acquire::ftp::Timeout "20";
Acquire::Retries "3";
APTEOF
fi

# ------------------------------------------------- system libraries, no fonts
# Ask Playwright itself which packages it wants — `--dry-run` prints the
# apt-get command instead of running it — then keep everything that is not a
# font. Deriving the list means a new Playwright dependency is picked up
# automatically; hardcoding it would rot silently and reintroduce exactly the
# launch failure this script is required to prevent.
deps="$(npx playwright install-deps --dry-run chromium 2>/dev/null \
        | tr ' ' '\n' \
        | grep -E '^(lib|xvfb|x11)' \
        | grep -vE '^(fonts-|xfonts-)' \
        | sort -u | tr '\n' ' ')"

if [ -n "${deps// /}" ]; then
  echo "Installing Playwright system libraries (fonts deliberately skipped): ${deps}"
  # These are already present on the runner image, so this is normally a
  # no-op that touches the network only for the package lists.
  sudo timeout "${ATTEMPT_SECONDS}" apt-get install -y --no-install-recommends ${deps} \
    || log_warn "system-library install returned non-zero; the launch proof below is the real gate"
else
  # Parsing produced nothing — Playwright changed its output, or npx failed.
  # Fall back to the original behaviour rather than guessing: slow, but never
  # a browser that cannot launch.
  log_warn "could not derive the dependency list; falling back to --with-deps (this may be slow)"
  sudo timeout "${ATTEMPT_SECONDS}" npx playwright install-deps chromium \
    || log_warn "install-deps returned non-zero; the launch proof below is the real gate"
fi

# ------------------------------------------------------- the browser (fast CDN)
# 173.8 MiB from Playwright's CDN measured at ~5 seconds, versus 38 minutes for
# 21.1 MB of fonts from the Ubuntu mirror. One retry covers a transient blip.
for attempt in 1 2; do
  timeout "${ATTEMPT_SECONDS}" npx playwright install chromium
  status=$?
  [ "${status}" -eq 0 ] && break
  if [ "${attempt}" -eq 2 ]; then
    log_err "playwright install chromium failed twice (exit ${status})"
    exit "${status}"
  fi
  log_warn "playwright install chromium failed (exit ${status}), retrying once"
done

# --------------------------------------------------------------- launch proof
# THE GATE. Skipping fonts is only safe because this runs: it starts the real
# browser and closes it. A missing shared library surfaces here as a red job
# instead of becoming a SKIP that quietly buys fewer journeys than the suite
# claims to run.
echo "Verifying Chromium actually launches..."
if ! timeout 120 node -e "require('@playwright/test').chromium.launch().then(b => b.close()).then(() => console.log('chromium launched OK')).catch(e => { console.error(e); process.exit(1); })"; then
  log_err "Chromium did not launch. The system-library set is insufficient — do NOT paper over this by re-adding fonts; find the missing lib (npx playwright install-deps --dry-run chromium)."
  exit 1
fi
