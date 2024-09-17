import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
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
        <AppButton
            data-umami-event="New Form button"
            data-umami-event-email={auth.email}
            className="min-w-[115px]"
            size={ButtonSize.Medium}
            onClick={async () => {
                router.push(`${environments.HTTP_SCHEME}${environments.DASHBOARD_DOMAIN}/${workspace?.workspaceName}/dashboard/form/create`);
            }}
        >
            New Form
        </AppButton>
    );
}
