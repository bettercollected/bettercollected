import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import GenericHalfModal from '@Components/common/generic-half-modal';

import { useModal } from '@app/components/modal-views/context';
import { useLazyGetStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';
import { formsApi } from '@app/store/redux/form-api';
import { workspacesApi } from '@app/store/workspaces/api';
import { forgetResponseList } from '@app/utils/response-list-memory';

export default function LogoutView(props: any) {
    const { closeModal } = useModal();
    const [trigger] = useLogoutMutation();
    const [authTrigger] = useLazyGetStatusQuery();
    const dispatch = useAppDispatch();

    const workspace = props?.workspace;

    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const asPath = `${pathname}${searchParams?.toString() ? '?' + searchParams.toString() : ''}`;

    const handleLogout = async () => {
        await trigger().then(async () => {
            await authTrigger();
            if (!props?.skipRedirect) {
                if (!!workspace && !!workspace?.workspaceName && props?.isClientDomain) router.push(asPath);
                else router.push('/login');
            }
            dispatch(setAuth(initialAuthState));
            // The next person at this browser must not see what this user saw (on the page Back
            // returns to, or from a cache): the cached workspaces, forms, responses and permissions,
            // and the responses list memory (whose search may be a responder's email).
            dispatch(workspacesApi.util.resetApiState());
            dispatch(formsApi.util.resetApiState());
            forgetResponseList();
            closeModal();
        });
    };

    return <GenericHalfModal headerTitle="Logout" title="Are you sure you want to logout?" type="danger" positiveText="Yes" negativeText="No" positiveAction={handleLogout} />;
}
