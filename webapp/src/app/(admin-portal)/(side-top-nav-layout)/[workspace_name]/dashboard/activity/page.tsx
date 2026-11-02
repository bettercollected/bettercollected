'use client';

import { ActivityGate } from '@app/components/audit-log/activity-list';

/**
 * The workspace's activity: who changed what, in plain sentences (docs/audit-log.md). Whoever holds audit.read sees it
 * while the server's AUDIT_LOG_UI_ENABLED is on; otherwise the sidebar never offers it and a direct visit goes back to
 * the forms list.
 */
export default function ActivityPage() {
    return <ActivityGate />;
}
