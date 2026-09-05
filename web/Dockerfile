FROM node:24-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=http://localhost:8000
ARG SITE_URL=http://localhost:3000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    SITE_URL=${SITE_URL}
RUN npm run build

FROM node:24-alpine AS runner

ENV NODE_ENV=production \
    PORT=3000

WORKDIR /app

COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

USER node

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
