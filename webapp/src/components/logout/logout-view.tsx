import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { useModal } from '@app/Components/modal-views/context';
import { useLazyGetStatusQuery, useLogoutMutation } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

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
            closeModal();
        });
    };

    return <GenericHalfModal headerTitle="Logout" title="Are you sure you want to logout?" type="danger" positiveText="Yes" negativeText="No" positiveAction={handleLogout} />;
}
