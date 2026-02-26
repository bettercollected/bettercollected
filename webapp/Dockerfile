# Install dependencies only when needed
FROM node:22-alpine AS base
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
#RUN apk add --no-cache libc6-compat
WORKDIR /app

FROM base AS prod
COPY ./webapp/package.json ./webapp/yarn.lock ./
RUN yarn install --prod --frozen-lockfile


# Rebuild the source code only when needed
FROM prod AS builder
ARG NEXT_PUBLIC_API_ENDPOINT_HOST
ARG NEXT_PUBLIC_NODE_ENV="production"

ENV NEXT_PUBLIC_API_ENDPOINT_HOST=$NEXT_PUBLIC_API_ENDPOINT_HOST \
    NEXT_PUBLIC_NODE_ENV=$NEXT_PUBLIC_NODE_ENV

RUN yarn install --frozen-lockfile
COPY --chown=node:node ./webapp .
RUN echo $NEXT_PUBLIC_API_ENDPOINT_HOST $NEXT_PUBLIC_NODE_ENV
RUN printenv
RUN yarn build
RUN rm -rf ./.next/cache/* && mkdir moveTarget && mv entrypoint.sh next.config.js next-i18next.config.js package.json next-sitemap.config.js public ./moveTarget
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
