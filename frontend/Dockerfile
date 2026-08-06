# Entropia V18 frontend — build with Node, serve static assets via nginx.
FROM node:26-alpine AS build
WORKDIR /app

# Vite inlines VITE_* at build time.
ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# nginx-unprivileged, not nginx: the stock image's master process runs as root
# (it needs CAP_NET_BIND_SERVICE for :80) and only the workers drop to `nginx`.
# The backend image has run as uid 10001 since it was written; this one was the
# last root process in the stack. The unprivileged variant is the same upstream
# nginx, prepared to run wholly as uid 101 with its pid/temp paths writable, and
# it listens on 8080 — which is why nginx.conf says `listen 8080`. The published
# HOST port is unchanged, so nothing outside the container moves.
FROM nginxinc/nginx-unprivileged:1.31-alpine AS runtime
# Deliberately NOT under conf.d/. The stock nginx.conf globs
# `include /etc/nginx/conf.d/*.conf` inside its `http` block, so a header file
# placed there is pulled in at http level as well as by the two explicit
# includes below — loaded three times, and reading like a standalone server
# block to anyone opening the directory. One level up, only the explicit
# includes reach it.
COPY nginx-security-headers.conf /etc/nginx/security-headers.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
