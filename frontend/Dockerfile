FROM node:24-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@11.25.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY backend/ ./backend-version/
COPY infra/ ./infra-version/
COPY compose.yaml ./compose-version.yaml
RUN pnpm run build

FROM nginx:stable-alpine
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
