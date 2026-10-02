# Development: the Vite dev server with hot reload (used by compose.dev.yaml)
FROM node:26-alpine AS dev
WORKDIR /app

# Install dependencies first, so this layer is cached until they change
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build the static files
FROM dev AS build
RUN npm run build

# Production: serve the built files with nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
