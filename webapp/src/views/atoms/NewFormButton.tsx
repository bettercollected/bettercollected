import { Button } from '@app/shadcn/components/ui/button';
import environments from '@app/configs/environments';
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
                router.push(`${environments.HTTP_SCHEME}${environments.DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/forms/create`);
            }}
        >
            New Form
        </Button>
    );
}
