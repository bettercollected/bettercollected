import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import Link from 'next/link';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DotIcon } from '@Components/Common/Icons/DotIcon';
import EditIcon from '@Components/Common/Icons/Edit';
import FormProviderIcon from '@Components/Common/Icons/FormProviderIcon';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';
import moment from 'moment/moment';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { GroupIcon } from '@app/components/icons/group-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS } from '@app/store/tours/types';

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    hasCustomDomain: boolean;
    index?: number;
    workspace: WorkspaceDto;
    isResponderPortal?: boolean;
    className?: string;
    group?: ResponderGroupDto;
    showPinned?: boolean;
    showVisibility?: boolean;
}

export default function WorkspaceFormCard({ form, hasCustomDomain, index, workspace, isResponderPortal = false, className = '', showPinned = true, showVisibility = true }: IWorkspaceFormCardProps) {
    const { openModal } = useModal();
    const router = useRouter();
    const { t } = useTranslation();
    const { deleteFormFromGroup } = useGroupForm();
    useEffect(() => {
        router.prefetch(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    }, [router]);

    const handleResponseClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    };

    const handleShareClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        openModal('SHARE_VIEW', {
            url: getShareUrl(),
            title: t(formConstant.shareThisForm)
        });
    };

    const getShareUrl = () => {
        const slug = form.settings?.customUrl;
        let shareUrl = '';
        if (window && typeof window !== 'undefined') {
            const scheme = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://`;
            const domainHost = hasCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${slug}`;
            shareUrl = scheme + domainHost;
        }
        return shareUrl;
    };
    const visibility = () => {
        if (form?.settings?.private) {
            return {
                icon: <GroupIcon className={'h-4 w-4'} />,
                type: 'Groups'
            };
        } else if (form?.settings?.hidden) {
            return {
                icon: <PrivateIcon />,
                type: t(localesCommon.hidden)
            };
        } else {
            return {
                icon: <PublicIcon />,
                type: t(localesCommon.public)
            };
        }
    };

    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[1px]  border-transparent hover:border-brand-200 transition cursor-pointer rounded-lg shadow-formCardDefault hover:shadow-formCard ${className}`}>
            <div className="rounded w-full group px-5 py-4 flex items-center justify-between">
                <div className=" flex flex-col gap-2 w-full">
                    <div className="flex gap-4 items-center flex-1 justify-between">
                        <div className="flex form-title gap-2">
                            <Tooltip title="">
                                <Typography className="h4-new" noWrap>
                                    {form?.title || t(localesCommon.untitled)}
                                </Typography>
                            </Tooltip>
                            {!isResponderPortal && !form?.isPublished && <div className="font-semibold text-xs text-black-600 rounded right-2 px-2 py-1 bg-gray-100">Draft</div>}
                        </div>
                        <div className="flex-1 lg:hidden">
                            <FormOptionsDropdownMenu className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS} redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                        </div>
                    </div>
                    <div className="flex items-center max-w-full flex-wrap gap-2">
                        <FormProviderIcon provider={form?.settings?.provider} />
                        {showVisibility && (
                            <Tooltip title={form?.settings?.private ? t(toolTipConstant.hideForm) : ''}>
                                <>
                                    <DotIcon />
                                    {form?.isPublished || isResponderPortal ? (
                                        <div className="flex items-center text-black-600">
                                            {visibility().icon}
                                            <p className={` text-sm ml-2 text-black-600`}>{visibility().type}</p>
                                        </div>
                                    ) : (
                                        <div className=" text-black-600 text-sm"> Last edited {moment.utc(form?.updatedAt).fromNow()}</div>
                                    )}
                                </>
                            </Tooltip>
                        )}

                        {!isResponderPortal && form?.isPublished && (
                            <>
                                <DotIcon />
                                <span className="text-sm text-black-600">
                                    {form?.responses} Response{(form?.responses || 0) > 1 && 's'}
                                </span>
                            </>
                        )}

                        {(form?.isPublished || isResponderPortal) && showPinned && form?.settings?.pinned && (
                            <>
                                <DotIcon />
                                <span className="text-sm text-[#FE3678]">Pinned</span>
                            </>
                        )}
                    </div>
                </div>
                {!isResponderPortal && (
                    <div className="hidden lg:invisible lg:group-hover:visible lg:flex gap-2 items-center">
                        {form?.isPublished ? (
                            form?.settings?.hidden ? (
                                <></>
                            ) : (
                                <AppButton onClick={handleShareClick} variant={ButtonVariant.Ghost} size={ButtonSize.Small} icon={<ShareIcon width={20} height={20} />}>
                                    Share
                                </AppButton>
                            )
                        ) : (
                            <></>
                        )}
                        <AppButton
                            onClick={() => {
                                router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`);
                            }}
                            variant={ButtonVariant.Ghost}
                            size={ButtonSize.Small}
                            icon={<EditIcon />}
                        >
                            Edit
                        </AppButton>
                        <FormOptionsDropdownMenu className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS} redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                    </div>
                )}
            </div>
        </div>
    );
}
