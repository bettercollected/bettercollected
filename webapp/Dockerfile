# Install dependencies only when needed
FROM node:18-alpine AS base
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
ARG NEXT_PUBLIC_API_ENDPOINT_HOST
ARG NEXT_PUBLIC_UNSPLASH_ACCESS_KEY
ARG NEXT_PUBLIC_DASHBOARD_DOMAIN
ARG NEXT_PUBLIC_FORM_DOMAIN
ARG SENTRY_DSN
ARG SENTRY_RELEASE
ARG SENTRY_URL
ARG SENTRY_ORG
ARG SENTRY_PROJECT
ARG SENTRY_AUTH_TOKEN
ARG SENTRY_LOG_LEVEL="debug"

RUN yarn install --frozen-lockfile
COPY --chown=node:node ./webapp .
RUN echo $NEXT_PUBLIC_API_ENDPOINT_HOST $NEXT_PUBLIC_DASHBOARD_DOMAIN $NEXT_PUBLIC_FORM_DOMAIN
RUN printenv
RUN yarn build
RUN rm -rf ./.next/cache/* && mkdir moveTarget && mv entrypoint.sh .sentryclirc sentry.client.config.js sentry.edge.config.js sentry.server.config.js sentry.properties next.config.js next-i18next.config.js package.json next-sitemap.config.js public ./moveTarget
# Production image, copy all the files and run next


FROM base

USER node

ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

CMD ["./entrypoint.sh"]

# You only need to copy next.config.js if you are NOT using the default configuration
# COPY --from=builder /app/next.config.js ./
COPY --from=prod --chown=node:node    /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/moveTarget/   ./
COPY --from=builder --chown=node:node /app/.next ./.next
VOLUME /home/node/.next/cache
