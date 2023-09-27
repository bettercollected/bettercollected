import {useEffect} from 'react';

import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import SmallLogo from '@Components/Common/Icons/SmallLogo';
import {Typography} from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import {TypeformIcon} from '@app/components/icons/brands/typeform';
import {GoogleFormIcon} from '@app/components/icons/google-form-icon';
import {useModal} from '@app/components/modal-views/context';
import {localesCommon} from '@app/constants/locales/common';
import {toolTipConstant} from '@app/constants/locales/tooltip';
import {useGroupForm} from '@app/lib/hooks/use-group-form';
import {StandardFormDto} from '@app/models/dtos/form';
import {ResponderGroupDto} from '@app/models/dtos/groups';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {JOYRIDE_CLASS} from '@app/store/tours/types';
import AppButton from "@Components/Common/Input/Button/AppButton";
import {ButtonSize, ButtonVariant} from "@Components/Common/Input/Button/AppButtonProps";
import EditIcon from "@Components/Common/Icons/Edit";
import ActiveLink from "@app/components/ui/links/active-link";
import ShareIcon from "@Components/Common/Icons/ShareIcon";
import {formConstant} from "@app/constants/locales/form";
import environments from "@app/configs/environments";
import moment from "moment/moment";

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    hasCustomDomain: boolean;
    index?: number;
    workspace: WorkspaceDto;
    isResponderPortal?: boolean;
    className?: string;
    group?: ResponderGroupDto;
}

export default function WorkspaceFormCard({
                                              form,
                                              hasCustomDomain,
                                              index,
                                              workspace,
                                              isResponderPortal = false,
                                              className = '',
                                              group
                                          }: IWorkspaceFormCardProps) {
    const {openModal} = useModal();
    const router = useRouter();
    const {t} = useTranslation();
    const {deleteFormFromGroup} = useGroupForm();
    useEffect(() => {
        router.prefetch(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    }, [router]);

    const handleResponseClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    };

    const handleShareClick = (event: any) => {
        event.preventDefault()
        event.stopPropagation()
        openModal('SHARE_VIEW', {
            url: getShareUrl(),
            title: t(formConstant.shareThisForm)
        })
    }


    const getShareUrl = () => {
        const slug = form.settings?.customUrl;
        let shareUrl = '';
        if (window && typeof window !== 'undefined') {
            const scheme = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://`;
            const domainHost = hasCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${slug}`;
            shareUrl = scheme + domainHost;
        }
        return shareUrl;
    }

    return (
        <div
            className={`flex flex-col items-start justify-between h-full bg-white border-[2px] border-transparent hover:border-black-500 transition cursor-pointer rounded-lg shadow-formCard ${className}`}>
            <div
                className="rounded w-full group px-5 py-4 flex items-center justify-between">
                <div className=" flex flex-col gap-2 w-full">
                    <div className="flex gap-4 items-center flex-1 justify-between">
                        <div className="flex form-title gap-2">
                            <Tooltip title="">
                                <Typography className="h4-new" noWrap>
                                    {form?.title || t(localesCommon.untitled)}
                                </Typography>
                            </Tooltip>
                            {!isResponderPortal && !form?.isPublished &&
                                <div
                                    className="font-semibold text-xs text-black-600 rounded right-2 px-2 py-1 bg-gray-100">Draft
                                </div>
                            }
                        </div>
                        <div className="flex-1 lg:hidden">
                            <FormOptionsDropdownMenu
                                className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS}
                                redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain}
                                workspace={workspace}/>
                        </div>
                    </div>
                    <div className="flex items-center max-w-full flex-wrap gap-2">
                        <div className="">
                            {form?.settings?.provider === 'typeform' &&
                                <div className="flex gap-2 text-sm items-center text-black-600"><TypeformIcon width={24}
                                                                                                              height={24}/>
                                    <span className="hidden lg:block">
                                    Typeform
                                </span>
                                </div>}
                            {form?.settings?.provider === 'google' &&
                                <div className="flex gap-2 text-sm items-center text-black-600">
                                    <GoogleFormIcon width={24} height={24} className="-ml-1"/>
                                    <span className="hidden lg:block">

                                    Google Form
                                </span></div>}
                            {form?.settings?.provider === 'self' &&
                                <div className="flex gap-2 items-center text-sm text-black-600">
                                    <SmallLogo height={24} width={24}/>
                                    <span className="hidden lg:block">
                                    bettercollected
                                </span>
                                </div>
                            }
                        </div>
                        {!isResponderPortal && (
                            <Tooltip title={form?.settings?.private ? t(toolTipConstant.hideForm) : ''}>
                                <>
                                    <DotDivider/>
                                    {
                                        form?.isPublished ?
                                            <div className="flex items-center text-black-600">
                                                {form?.settings?.private ? <PrivateIcon/> : <PublicIcon/>}
                                                <p className={` text-sm ml-2 text-black-600`}>{form?.settings?.private ? t(localesCommon.hidden) : t(localesCommon.public)}</p>
                                            </div>
                                            : <div className=" text-black-600 text-sm"> Last
                                                edited {moment(form?.updatedAt).fromNow()}</div>
                                    }
                                </>
                            </Tooltip>
                        )}

                        {!isResponderPortal && form?.isPublished && (
                            <>
                                <DotDivider/>
                                <span className="text-sm text-black-600">

                                {form?.responses} Response{((form?.responses || 0) > 1) && "s"}
                                </span>
                            </>
                        )}

                        {!isResponderPortal && form?.isPublished && form?.settings?.pinned && (
                            <>
                                <DotDivider/>
                                <span className="text-sm text-[#FE3678]">
                                Pinned
                                </span>
                            </>
                        )}
                    </div>
                </div>
                {
                    !isResponderPortal && (
                        <div className="hidden lg:invisible lg:group-hover:visible lg:flex gap-2 items-center">
                            {
                                form?.isPublished &&
                                <AppButton onClick={handleShareClick}
                                           variant={ButtonVariant.Ghost} size={ButtonSize.Small}
                                           icon={<ShareIcon width={20} height={20}/>}>Share</AppButton>
                            }
                            <ActiveLink key={'edit'}
                                        href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`}>
                                <AppButton variant={ButtonVariant.Ghost} size={ButtonSize.Small}
                                           icon={<EditIcon/>}>Edit</AppButton>
                            </ActiveLink>
                            <FormOptionsDropdownMenu
                                className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS}
                                redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain}
                                workspace={workspace}/>
                        </div>
                    )
                }
            </div>
        </div>
    );
}


function DotDivider() {
    return (
        <div className="h-1 w-1 rounded-full bg-black-600 mx-2"/>
    )
}
