import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DotIcon } from '@Components/Common/Icons/Common/DotIcon';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import ShareIcon from '@Components/Common/Icons/Common/ShareIcon';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import PrivateIcon from '@Components/Common/Icons/Form/Private';
import PublicIcon from '@Components/Common/Icons/Form/Public';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Typography } from '@mui/material';
import moment from 'moment/moment';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { GroupIcon } from '@app/components/icons/group-icon';
import { useModal } from '@app/components/modal-views/context';
import DeleteDropDown from '@app/components/ui/delete-dropdown';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS } from '@app/store/tours/types';
import getFormShareURL from '@app/utils/formUtils';
import { validateFormOpen } from '@app/utils/validationUtils';

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

export default function WorkspaceFormCard({ form, hasCustomDomain, group, workspace, isResponderPortal = false, className = '', showPinned = true, showVisibility = true }: IWorkspaceFormCardProps) {
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
            url: getFormShareURL(form, workspace),
            title: t(formConstant.shareThisForm)
        });
    };

    const visibility = () => {
        if (form?.settings?.hidden) {
            return {
                icon: <PrivateIcon />,
                type: t(localesCommon.hidden)
            };
        } else if (form?.settings?.private) {
            return {
                icon: <GroupIcon className={'h-4 w-4'} />,
                type: t('GROUP.GROUPS')
            };
        } else {
            return {
                icon: <PublicIcon />,
                type: t(localesCommon.public)
            };
        }
    };

    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);

    return (
        <div className={`hover:border-brand-200 shadow-formCardDefault hover:shadow-formCard flex h-full cursor-pointer flex-col  items-start justify-between rounded-lg border-[1px] border-transparent bg-white transition ${className}`}>
            <div className="group flex w-full items-center justify-between rounded px-5 py-4">
                <div className=" flex w-full flex-col gap-2">
                    <div className="flex flex-1 items-center justify-between gap-4">
                        <div className="form-title flex gap-2">
                            <Tooltip title="">
                                <Typography className="h4-new">{form?.title || t(localesCommon.untitled)}</Typography>
                            </Tooltip>
                            {!isResponderPortal && !form?.isPublished && <div className="text-black-600 right-2 rounded bg-gray-100 px-2 py-1 text-xs font-semibold">{t('FORM.DRAFT')}</div>}
                            {!isResponderPortal && form?.isPublished && !isFormOpen && <div className="text-black-600 right-2 rounded bg-gray-100 px-2 py-1 text-xs font-semibold">{t('FORM.CLOSED')}</div>}
                            {!isResponderPortal && form?.builderVersion === 'v2' && <div className="text-black-600 right-2 rounded bg-gray-100 px-2 py-1 text-xs font-semibold">V2</div>}
                        </div>
                        {!group && !isResponderPortal && (
                            <div className="flex-1 lg:hidden">
                                <FormOptionsDropdownMenu className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS} redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                            </div>
                        )}
                    </div>
                    <div className="flex max-w-full flex-wrap items-center gap-2">
                        <FormProviderIcon provider={form?.settings?.provider} />
                        {showVisibility && (
                            <Tooltip title={form?.settings?.private ? t(toolTipConstant.hideForm) : ''}>
                                <div className="fap-2 flex items-center">
                                    <DotIcon />
                                    {form?.isPublished || isResponderPortal ? (
                                        <div className="text-black-600 flex items-center">
                                            {visibility().icon}
                                            <p className={` text-black-600 ml-2 text-sm`}>{visibility().type}</p>
                                        </div>
                                    ) : (
                                        <div className=" text-black-600 text-sm">
                                            {t('FORM.LAST_EDITED')} {moment.utc(form?.updatedAt).fromNow()}
                                        </div>
                                    )}
                                </div>
                            </Tooltip>
                        )}

                        {!isResponderPortal && form?.isPublished && (
                            <>
                                <DotIcon />
                                <span className="text-black-600 text-sm">
                                    {form?.responses} {t(`FORM.RESPONSE${(form?.responses || 0) > 1 ? 'S' : ''}`)}
                                </span>
                            </>
                        )}

                        {(form?.isPublished || isResponderPortal) && showPinned && form?.settings?.pinned && (
                            <>
                                <DotIcon />
                                <span className="text-sm text-[#FE3678]">{t('FORM.PINNED')}</span>
                            </>
                        )}
                    </div>
                </div>
                {!isResponderPortal && !group && (
                    <div className="hidden items-center gap-2 lg:invisible lg:flex lg:group-hover:visible">
                        {form?.isPublished && !form?.settings?.hidden && isFormOpen && (
                            <AppButton onClick={handleShareClick} variant={ButtonVariant.Ghost} size={ButtonSize.Small} icon={<ShareIcon width={16} height={16} />}>
                                {t('BUTTON.SHARE')}
                            </AppButton>
                        )}
                        {form?.settings?.provider === 'self' && (
                            <AppButton
                                onClick={(event: any) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    const editFormUrl = form?.builderVersion === 'v2' ? `/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit` : `/${workspace.workspaceName}/dashboard/forms/${form.formId}/v1/edit`;
                                    if (form?.builderVersion === 'v2') {
                                        router.push(environments.HTTP_SCHEME + environments.V2_BUILDER_DOMAIN + editFormUrl);
                                    } else {
                                        router.push(editFormUrl);
                                    }
                                }}
                                variant={ButtonVariant.Ghost}
                                size={ButtonSize.Small}
                                icon={<EditIcon width={16} height={16} />}
                            >
                                {t('BUTTON.EDIT')}
                            </AppButton>
                        )}
                        <FormOptionsDropdownMenu className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS} redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                    </div>
                )}
                {!!group && (
                    <DeleteDropDown
                        className="lg:invisible lg:group-hover:visible"
                        onDropDownItemClick={(event) => {
                            event.stopPropagation();
                            event.preventDefault();
                            openModal('DELETE_CONFIRMATION', {
                                positiveText: 'Remove',
                                headerTitle: 'Remove Form',
                                title: t(localesCommon.remove) + ' ' + form.title,
                                handleDelete: () => deleteFormFromGroup({ group, workspaceId: workspace.id, form })
                            });
                        }}
                    />
                )}
            </div>
        </div>
    );
}
