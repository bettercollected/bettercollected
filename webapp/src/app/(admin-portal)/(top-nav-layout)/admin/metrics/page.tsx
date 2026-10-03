import type { Metadata } from 'next';

import PlatformMetricsView from './_components/platform-metrics-view';

// Platform admins only (ADMIN role, not workspace admins). "admin" is a
// reserved workspace handle in the backend, so this static route can never
// shadow a workspace's /[workspace_name]/... pages.
export const metadata: Metadata = {
    title: 'Platform metrics',
    robots: { index: false, follow: false }
};

export default function PlatformMetricsPage() {
    return <PlatformMetricsView />;
}
