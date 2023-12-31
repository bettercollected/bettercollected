import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { useLazyGetLogoutQuery, useLazyGetStatusQuery } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

export default function LogoutView(props: any) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [trigger] = useLazyGetLogoutQuery();
    const [authTrigger] = useLazyGetStatusQuery();
    const dispatch = useAppDispatch();

    const workspace = props?.workspace;

    const router = useRouter();
    const language = router?.locale === 'en' ? '' : `${router.locale}/`;
    const handleLogout = async () => {
        await trigger().then(async () => {
            await authTrigger();
            if (!!workspace && !!workspace?.workspaceName && !!props?.isclientdomain && props.isclientdomain === 'true') router.push(`/${workspace.workspaceName}`);
            else router.push(`/${language}login`);
            dispatch(setAuth(initialAuthState));
            closeModal();
        });
    };

    return <GenericHalfModal headerTitle="Logout" title="Are you sure you want to logout?" type="danger" positiveText="Yes" negativeText="No" positiveAction={handleLogout} />;
}
