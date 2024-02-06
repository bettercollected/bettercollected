import React from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
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
import { localesCommon } from '@app/constants/locales/common';
import { profileMenu } from '@app/constants/locales/profile-menu';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { getFullNameFromUser } from '@app/utils/userUtils';

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
        <div className={`max-h-screen h-screen !bg-new-white-200 opacity-100 max-w-screen w-screen overflow-auto flex flex-col p-5 md:p-10 md:flex-row ${!hasCustomDomain ? '!pb-20' : ''}`}>
            <div className="max-w-screen w-full md:max-w-[320px] md:sticky md:top-0">
                <div className="rounded-xl bg-white w-full">
                    {workspace.bannerImage && (
                        <div className="w-full relative aspect-banner-mobile rounded-t-2xl">
                            <Image src={workspace.bannerImage} className="rounded-t-2xl" alt="Worksace Banner" layout="fill" />
                        </div>
                    )}
                    {workspace.profileImage && (
                        <div className={`${workspace.bannerImage ? 'relative top-[-36px] left-6' : 'relative top-6 ml-6'} w-16 h-16`}>
                            <Image src={workspace.profileImage} alt="Profile Image" className="rounded-xl" layout="fill" />
                        </div>
                    )}

                    <div className={`${workspace.bannerImage ? '-mt-8' : 'mt-4'}  p-6`}>
                        <div className="h3-new">{workspace?.title || 'Untitled Workspace'}</div>
                        {workspace?.description && <div className="mt-2 text-black-600">{workspace.description}</div>}
                        <div className="mt-4 flex gap-6 text-new-black-800 p4-new">
                            <ActiveLink target="_blank" className="p4-new !leading-none !not-italic !text-black-800" href={workspace.terms_of_service_url ?? `https://bettercollected.com/terms-of-service/`}>
                                {t(localesCommon.termsOfServices.title)}
                            </ActiveLink>
                            <ActiveLink target="_blank" className="p4-new !leading-none !not-italic !text-black-800" href={workspace.privacy_policy_url ?? `https://bettercollected.com/privacy-policy/`}>
                                {t(localesCommon.privacyPolicy.title)}
                            </ActiveLink>
                        </div>
                    </div>
                </div>
                {!auth.id && !auth.isLoading && (
                    <div className="p-6 bg-white rounded-xl mt-6 flex flex-col">
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
                    <div className="bg-white mt-6  rounded-xl w-full ">
                        <Disclosure>
                            {({ open }) => (
                                <>
                                    <Disclosure.Button className="flex gap-2 p-4 w-full items-center justify-between cursor-pointer">
                                        <div className="flex gap-2">
                                            <AuthAccountProfileImage size={36} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                                            <div className="flex flex-col gap-2 text-start justify-center !text-black-700 pr-1">
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
                                                <div className="p-4 p4-new text-black-600">
                                                    You have 0 workspace associated with this email.{' '}
                                                    <ActiveLink target="_blank" href="https://bettercollected.com" className="text-blue-500">
                                                        Try Bettercollected{' '}
                                                    </ActiveLink>
                                                </div>
                                            </>
                                        )}
                                        <Divider className="text-black-200" />
                                        <div className="m-2 p-2 flex gap-2 text-black-600 hover:bg-new-blue-100 rounded cursor-pointer active:bg-blue-100" onClick={handleLogout}>
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
                    className="bg-white w-full xl:hidden my-6 p2-new p-4 cursor-pointer rounded-xl"
                    onClick={() => {
                        openModal('SEARCH_BY_SUBMISSION_NUMBER');
                    }}
                >
                    Search your form response by submission number
                </div>

                {!hasCustomDomain && (
                    <div className="bg-white w-full hidden md:flex mt-6 rounded p-3 shadow-powered-by gap-2">
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
