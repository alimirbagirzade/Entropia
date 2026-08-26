# Entropia V18 frontend — build with Node, serve static assets via nginx.
FROM node:26-alpine AS build
WORKDIR /app

# Vite inlines VITE_* at build time.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# No glob on package-lock.json. `package-lock.json*` matched zero files without
# complaint, so a context missing its lockfile still built — npm then resolved
# the `^` ranges in package.json freely, and the image's dependency tree became
# whatever had been published that morning. Naming the file exactly turns the
# missing-lockfile case into a hard COPY failure instead of silent re-resolution.
COPY package.json package-lock.json ./
# `npm ci`, not `npm install`: ci installs the lockfile as written and exits
# non-zero when package.json and the lockfile disagree, where install quietly
# reconciles them and rewrites the lock. Measured on this tree today the two
# produce byte-identical bundles — the point is that only one of them is
# guaranteed to keep doing so.
RUN npm ci
# COPY . . lands AFTER the install and can overwrite /app/node_modules with a
# host copy. frontend/.dockerignore is what prevents that; without it the
# `npm ci` above is cosmetic.
COPY . .
RUN npm run build

# The CSP's connect-src origin has to be the SAME origin Vite just inlined into
# the bundle, so it is derived here from the one variable both sides read rather
# than written down twice. `read_only: true` on the web container rules out
# nginx's runtime envsubst entrypoint, and a runtime value could in any case only
# ever disagree with what the bundle was built against.
#
# The `! grep` line is the fail-closed half: if the placeholder survives (a
# renamed token, a botched sed) the image build STOPS, rather than shipping a
# CSP whose connect-src is the literal string `__API_ORIGIN__` — which would
# block every API call at runtime, in the browser, long after CI went green.
RUN set -eu; \
    origin="$(printf '%s' "$VITE_API_BASE_URL" \
      | sed -n 's#^\([A-Za-z][A-Za-z0-9+.-]*://[^/]*\).*#\1#p')"; \
    sed "s#__API_ORIGIN__#${origin}#" nginx-security-headers.conf \
      > /security-headers.conf; \
    ! grep -q '__API_ORIGIN__' /security-headers.conf

# nginx-unprivileged, not nginx: the stock image's master process runs as root
# (it needs CAP_NET_BIND_SERVICE for :80) and only the workers drop to `nginx`.
# The backend image has run as uid 10001 since it was written; this one was the
# last root process in the stack. The unprivileged variant is the same upstream
# nginx, prepared to run wholly as uid 101 with its pid/temp paths writable, and
# it listens on 8080 — which is why nginx.conf says `listen 8080`. The published
# HOST port is unchanged, so nothing outside the container moves.
FROM nginxinc/nginx-unprivileged:1.31-alpine AS runtime
# The base tag still ships openssl 3.5.7-r0, which carries CVE-2026-14456
# (unbounded memory growth in the QUIC server, HIGH, fixed in 3.5.8-r0). The
# tag is floating, so this resolves itself the moment upstream rebuilds — until
# then the release gate fails on a finding that HAS a published fix, and the
# only alternatives were waiving it in .github/security-allowlist.json (an
# exception needs a named owner and an expiry; nothing is currently waived and
# that is the goal state) or pinning a digest we would then have to chase.
# `apk upgrade` is scoped to the two openssl packages so it cannot quietly pull
# an unrelated version bump into the runtime layer.
#
# This is the ONE root step in this stage and it exists only for the duration of
# the upgrade: `USER 101` is restored immediately, because running wholly as
# uid 101 is the entire reason this image is the `-unprivileged` variant (see
# the note above). Do not let a later edit leave the stage as root.
USER root
RUN apk upgrade --no-cache libcrypto3 libssl3
USER 101
# Deliberately NOT under conf.d/. The stock nginx.conf globs
# `include /etc/nginx/conf.d/*.conf` inside its `http` block, so a header file
# placed there is pulled in at http level as well as by the two explicit
# includes below — loaded three times, and reading like a standalone server
# block to anyone opening the directory. One level up, only the explicit
# includes reach it.
# The GENERATED copy, not the source: the source still carries the
# __API_ORIGIN__ placeholder, and the build stage above is what resolves it.
COPY --from=build /security-headers.conf /etc/nginx/security-headers.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
