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

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-center gap-8 justify-between p-10">
                    {/* <Logout className="text-6xl text-red-500" /> */}
                    <h4 className="sh1">{t(localesCommon.logoutMessage)}</h4>

                    <div className="flex w-full gap-4 justify-end">
                        <AppButton className={'w-full'} data-testid="logout-button" variant={ButtonVariant.Danger} onClick={handleLogout}>
                            {t(buttonConstant.logout)}
                        </AppButton>
                        <AppButton className={'w-full'} variant={ButtonVariant.Secondary} onClick={closeModal}>
                            {t(buttonConstant.cancel)}
                        </AppButton>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={closeModal}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
