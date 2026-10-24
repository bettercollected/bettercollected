'use client';

import { useEffect } from 'react';

import { useParams, useRouter } from 'next/navigation';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { defaultAiTabUrl } from '@app/lib/workspace-sections';

/**
 * /dashboard/ai opens the first tab this member may use: Profile for those
 * who manage AI, Memory for everyone else. Permissions load in the browser,
 * so the redirect does too.
 */
export default function AIPage() {
    const router = useRouter();
    const params = useParams<{ workspace_name: string }>();
    const { can, ready } = useWorkspacePermissions();

    useEffect(() => {
        if (!ready) return;
        router.replace(defaultAiTabUrl(params?.workspace_name, can));
    }, [ready, can, params?.workspace_name, router]);

    return null;
}
