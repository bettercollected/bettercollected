import * as Sentry from '@sentry/nextjs';

import environments from '@app/configs/environments';

const SENTRY_DSN = environments.SENTRY_DSN ?? '';

Sentry.init({
    dsn: SENTRY_DSN,
    debug: true,
    environment: environments.NEXT_PUBLIC_NODE_ENV,

    // Set tracesSampleRate to 1.0 to capture 100%
    // of transactions for performance monitoring.
    // We recommend adjusting this value in production
    tracesSampleRate: 1.0

    // ...

    // Note: if you want to override the automatic release value, do not set a
    // `release` value here - use the environment variable `SENTRY_RELEASE`, so
    // that it will also get attached to your source maps
});
