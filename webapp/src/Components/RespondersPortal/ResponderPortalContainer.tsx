import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import { Disclosure } from '@headlessui/react';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import FormsAndSubmissionsTabContainer from '@app/components/forms-and-submisions-tabs/forms-and-submisisons-tab-container';
import { ChevronDown } from '@app/components/icons/chevron-down';
import { Logout } from '@app/components/icons/logout-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import Logo from '@app/components/ui/logo';
import PoweredBy from '@app/components/ui/powered-by';
import environments from '@app/configs/environments';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { getFullNameFromUser } from '@app/utils/userUtils';
import WorkspaceDetailsCard from './WorkspaceDetailsCard';

export default function ResponderPortalContainer(props: { workspace: WorkspaceDto; hasCustomDomain: boolean }) {
    const { workspace, hasCustomDomain } = props;
    const { t } = useTranslation();
    const auth = useAppSelector(selectAuth);

    const isClientDomain = window?.location?.origin !== environments.ADMIN_DOMAIN;

    const router = useRouter();

    const { openModal } = useModal();

    const handleLogout = () => {
        openModal('LOGOUT_VIEW', { workspace, isClientDomain });
    };

    return (
        <div className={`!bg-new-white-200 max-w-screen flex h-screen max-h-screen w-screen flex-col overflow-auto p-5 opacity-100 md:flex-row md:p-10 ${!hasCustomDomain ? '!pb-20' : ''}`}>
            <div className="max-w-screen w-full md:sticky md:top-0 md:w-[320px] md:max-w-[320px]">
                <WorkspaceDetailsCard workspace={workspace} />
                {!auth.id && !auth.isLoading && (
                    <div className="mt-6 flex flex-col rounded-xl bg-white p-6">
                        <div className="h4-new">Check my data</div>
                        <div className="p2-new text-black-600 mt-2">Verify your email address to view all the data associated with you.</div>
                        <AppButton
                            className="mt-6"
                            size={ButtonSize.Small}
                            onClick={() => {
                                router.push({
                                    pathname: '/login',
                                    query: {
                                        type: 'responder',
                                        workspace_id: workspace.id,
                                        redirect_to: router.asPath
                                    }
                                });
                            }}
                        >
                            Verify Now
                        </AppButton>
                    </div>
                )}
                {auth.id && (
                    <div className="mt-6 w-full  rounded-xl bg-white ">
                        <Disclosure>
                            {({ open }) => (
                                <>
                                    <Disclosure.Button className="flex w-full cursor-pointer items-center justify-between gap-2 p-4">
                                        <div className="flex gap-2">
                                            <AuthAccountProfileImage size={36} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                                            <div className="!text-black-700 flex flex-col justify-center gap-2 pr-1 text-start">
                                                <span className="body6 !leading-none">{getFullNameFromUser(auth)?.trim() || auth?.email || ''}</span>
                                                <span className="body5 !leading-none">{auth?.email} </span>
                                            </div>
                                        </div>
                                        <ChevronDown className={`${open ? 'rotate-180 transform' : ''} h-3 w-3 text-blue-900`} />
                                    </Disclosure.Button>
                                    <Disclosure.Panel className="pb-2">
                                        {!auth?.roles?.includes('FORM_CREATOR') && (
                                            <>
                                                <Divider className="text-black-200" />
                                                <div className="p4-new text-black-600 p-4">
                                                    You have 0 workspace associated with this email.{' '}
                                                    <ActiveLink target="_blank" href="https://bettercollected.com" className="text-blue-500">
                                                        Try Bettercollected{' '}
                                                    </ActiveLink>
                                                </div>
                                            </>
                                        )}
                                        <Divider className="text-black-200" />
                                        <div className="text-black-600 hover:bg-new-blue-100 m-2 flex cursor-pointer gap-2 rounded p-2 active:bg-blue-100" onClick={handleLogout}>
                                            <Logout width={24} height={24} />
                                            <span>{t(profileMenu.logout)}</span>
                                        </div>
                                    </Disclosure.Panel>
                                </>
                            )}
                        </Disclosure>
                    </div>
                )}

                <div
                    className="p2-new my-6 w-full cursor-pointer rounded-xl bg-white p-4 xl:hidden"
                    onClick={() => {
                        openModal('SEARCH_BY_SUBMISSION_NUMBER');
                    }}
                >
                    Search your form response by submission number
                </div>

                {!hasCustomDomain && (
                    <div className="shadow-powered-by mt-6 hidden w-full gap-2 rounded bg-white p-3 md:flex">
                        <span className="body3 text-black-700">Powered by:</span>
                        <Logo showProTag={false} isLink={false} isCustomDomain className="h-[14px] w-fit" />
                    </div>
                )}
            </div>
            <div className="flex-1">
                <FormsAndSubmissionsTabContainer isFormCreator={false} workspace={workspace} workspaceId={workspace.id} showResponseBar={!!auth.id} />
            </div>
            <div className="lg:hidden">
                <PoweredBy />
            </div>
        </div>
    );
}
