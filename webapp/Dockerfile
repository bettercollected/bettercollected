# Install dependencies only when needed
FROM node:16-alpine AS base
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
#RUN apk add --no-cache libc6-compat
WORKDIR /home/node
USER node

FROM base AS prod
COPY package.json yarn.lock ./
RUN yarn install --prod


# Rebuild the source code only when needed
FROM prod as builder
ARG BASE_DEPLOY_PATH=
ARG NEXT_PUBLIC_NODE_ENV="development"
RUN yarn install 
COPY --chown=node:node . .
RUN  BASE_DEPLOY_PATH=${BASE_DEPLOY_PATH} NEXT_PUBLIC_NODE_ENV=${NEXT_PUBLIC_NODE_ENV}  yarn build 
RUN rm -rf ./.next/cache/*
# Production image, copy all the files and run next
FROM base
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Uncomment the following line in case you want to disable telemetry.
CMD ["./entrypoint.sh"]

# You only need to copy next.config.js if you are NOT using the default configuration
# COPY --from=builder /app/next.config.js ./
COPY --from=prod    /home/node/node_modules ./node_modules
COPY --from=builder  /home/node/next.config.js /home/node/next-i18next.config.js /home/node/package.json /home/node/next-sitemap.config.js /home/node/public /home/node/entrypoint.sh   ./
COPY --from=builder  /home/node/.next ./.next
VOLUME /home/node/.next/cache
