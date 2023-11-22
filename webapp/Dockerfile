# Install dependencies only when needed
FROM node:16-alpine AS base
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
#RUN apk add --no-cache libc6-compat
WORKDIR /app

FROM base AS prod
COPY ./webapp/package.json ./webapp/yarn.lock ./
RUN yarn install --prod --frozen-lockfile


# Rebuild the source code only when needed
FROM prod as builder
ARG BASE_DEPLOY_PATH
ARG NEXT_PUBLIC_NODE_ENV="production"
ARG SENTRY_DSN
ARG SENTRY_RELEASE
ARG SENTRY_URL
ARG SENTRY_ORG
ARG SENTRY_PROJECT
ARG SENTRY_AUTH_TOKEN
ARG SENTRY_LOG_LEVEL="debug"
RUN yarn install --frozen-lockfile
COPY --chown=node:node ./webapp .
RUN  BASE_DEPLOY_PATH=${BASE_DEPLOY_PATH} SENTRY_DSN=${SENTRY_DSN} SENTRY_RELEASE=${SENTRY_RELEASE} SENTRY_URL=${SENTRY_URL} SENTRY_ORG=${SENTRY_ORG} SENTRY_PROJECT=${SENTRY_PROJECT} SENTRY_AUTH_TOKEN=${SENTRY_AUTH_TOKEN} SENTRY_LOG_LEVEL=${SENTRY_LOG_LEVEL} NEXT_PUBLIC_NODE_ENV=${NEXT_PUBLIC_NODE_ENV} yarn build
RUN rm -rf ./.next/cache/* && mkdir moveTarget && mv entrypoint.sh .sentryclirc sentry.client.config.js sentry.edge.config.js sentry.server.config.js sentry.properties next.config.js next-i18next.config.js package.json next-sitemap.config.js public ./moveTarget
# Production image, copy all the files and run next


FROM base

USER node

ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

HEALTHCHECK CMD curl -i http://localhost:3000

CMD ["./entrypoint.sh"]

# You only need to copy next.config.js if you are NOT using the default configuration
# COPY --from=builder /app/next.config.js ./
COPY --from=prod    /app/node_modules ./node_modules
COPY --from=builder  /app/moveTarget/   ./
COPY --from=builder  /app/.next ./.next
VOLUME /home/node/.next/cache
