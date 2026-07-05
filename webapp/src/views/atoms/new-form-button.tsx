"use client";
import { Button } from '@app/shadcn/components/ui/button';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useRouter } from 'next/navigation';

export default function NewFormButton() {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const auth = useAppSelector(selectAuth);
    return (
        <Button
            data-umami-event="New Form button"
            data-umami-event-email={auth.email}
            className="min-w-[115px]"
            size="medium"
            onClick={async () => {
                router.push(`${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/forms/create`);
            }}
        >
            New Form
        </Button>
    );
}
