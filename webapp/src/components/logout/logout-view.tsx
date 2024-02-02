import { useRouter } from 'next/router';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { useModal } from '@app/components/modal-views/context';
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
    const language = router?.locale === 'en' ? '' : `${router.locale}/`;
    const handleLogout = async () => {
        await trigger().then(async () => {
            await authTrigger();
            if (!props?.skipRedirect) {
                if (!!workspace && !!workspace?.workspaceName && props?.isClientDomain) router.push(router.asPath);
                else router.push(`/${language}login`);
            }
            dispatch(setAuth(initialAuthState));
            closeModal();
        });
    };

    return <GenericHalfModal headerTitle="Logout" title="Are you sure you want to logout?" type="danger" positiveText="Yes" negativeText="No" positiveAction={handleLogout} />;
}
