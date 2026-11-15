'use client';

import { ActivityGate } from '@app/components/audit-log/activity-list';
import { PageSurface } from '@app/components/ui/page-surface';

/**
 * The workspace's activity: who changed what, in plain sentences (docs/audit-log.md). Whoever holds audit.read sees it
 * while the server's AUDIT_LOG_UI_ENABLED is on; otherwise the sidebar never offers it and a direct visit goes back to
 * the forms list.
 */
export default function ActivityPage() {
    // the workspace's page is wide and sits on the page surface; the list's own 860 px column and bottom room are for a form's page
    return (
        <PageSurface className="[&_[data-testid=activity-list]]:max-w-none [&_[data-testid=activity-list]]:pb-0">
            <ActivityGate />
        </PageSurface>
    );
}
