import { Suspense } from 'react';

import environments from '@app/configs/environments';
import { dashboardOrigin } from '@app/lib/google-oauth-popup';

import GoogleCallbackContent from './callback-content';

export default function GoogleCallbackPage() {
    // From the server's configuration on each request (the root layout is
    // dynamic), so the target is known before the page's scripts run.
    const origin = dashboardOrigin(environments.HTTP_SCHEME, environments.DASHBOARD_DOMAIN);
    return (
        <Suspense fallback={null}>
            <GoogleCallbackContent dashboardOrigin={origin} />
        </Suspense>
    );
}
