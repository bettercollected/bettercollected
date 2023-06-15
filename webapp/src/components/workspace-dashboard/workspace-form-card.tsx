import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import PinnedIcon from '@Components/Common/Icons/Pinned';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import Share from '@Components/Common/Icons/Share';
import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';
import { Button, Typography } from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useGroupForm } from '@app/lib/hooks/use-group-form';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { selectIsAdmin } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { getFormUrl } from '@app/utils/urlUtils';

import DeleteDropDown from '../ui/delete-dropdown';

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    hasCustomDomain: boolean;
    index?: number;
    workspace?: WorkspaceDto;
    isResponderPortal?: boolean;
    className?: string;
    group?: ResponderGroupDto;
}

export default function WorkspaceFormCard({ form, hasCustomDomain, index, workspace, isResponderPortal = false, className = '', group }: IWorkspaceFormCardProps) {
    const { openModal } = useModal();
    const router = useRouter();
    const { t } = useTranslation();
    const { deleteFormFromGroup } = useGroupForm();
    const isAdmin = useAppSelector(selectIsAdmin);
    useEffect(() => {
        router.prefetch(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    }, [router]);

    const handleResponseClick = (event: any) => {
        event.preventDefault();
        event.stopPropagation();
        router.push(`/${workspace?.workspaceName}/dashboard/forms/${form.formId}?view=Responses`);
    };
    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[2px] border-transparent hover:border-black-500 transition cursor-pointer rounded-lg shadow-formCard ${className}`}>
            {typeof index !== undefined && index === 0 && environments.ENABLE_JOYRIDE_TOURS && !isResponderPortal && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION}
                    placement="top"
                    steps={[
                        {
                            title: <JoyrideStepTitle text="View form responses" />,
                            content: <JoyrideStepContent>You can see total responses in each form here and navigate to the responses page.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_RESPONSES}`,
                            placementBeacon: 'bottom-start'
                        },
                        {
                            title: <JoyrideStepTitle text="Share your form" />,
                            content: <JoyrideStepContent>You can use this button to share your form to your desired audience.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_SHARE}`,
                            placementBeacon: 'bottom-start'
                        },
                        {
                            title: <JoyrideStepTitle text="Update form settings" />,
                            content: <JoyrideStepContent>You can use this button to view the available options and settings of the form, or navigate inside individual form page to view it&apos;s settings.</JoyrideStepContent>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS}`,
                            placementBeacon: 'bottom-start'
                        }
                    ]}
                />
            )}
            <div className="rounded relative w-full px-4 py-6 flex min-h-28 flex-col gap-4 items-start justify-between overflow-hidden">
                <div className="rounded h-[34px] w-[34px]">{form?.settings?.provider === 'typeform' ? <TypeformIcon width={34} height={34} /> : <GoogleFormIcon width={34} height={34} className="-ml-1" />}</div>
                <Tooltip title="">
                    <Typography className="body3 !leading-none w-[inherit]" noWrap>
                        {form?.title || t(localesCommon.untitled)}
                    </Typography>
                </Tooltip>
                {!isResponderPortal && (
                    <Tooltip title={form?.settings?.private ? t(toolTipConstant.hideForm) : ''}>
                        <div className="flex items-center">
                            {form?.settings?.private ? <PrivateIcon /> : <PublicIcon />}
                            <p className={`leading-none text-[12px] text-black-900 ml-2`}>{form?.settings?.private ? t(localesCommon.hidden) : t(localesCommon.public)}</p>
                        </div>
                    </Tooltip>
                )}
                {!isResponderPortal && form?.settings?.pinned && (
                    <Tooltip className="absolute top-2 right-2 bg-white " title={t(toolTipConstant.pinned)}>
                        <div onClick={(e: any) => e.preventDefault()}>
                            <PinnedIcon />
                        </div>
                    </Tooltip>
                )}
            </div>
            {!isResponderPortal && !!workspace && (
                <div className="relative flex justify-between items-center py-2 px-4 gap-4 w-full border-t-[1px] border-black-400">
                    <Button className={`p-2 capitalize hover:bg-brand-100 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_RESPONSES}`} variant="text" onClick={handleResponseClick}>
                        <span className="body4">
                            {form?.responses} {!!form?.responses && form.responses > 1 ? t(formConstant.responses) : t(formConstant.response)}
                        </span>
                    </Button>
                    {!group && (
                        <div className="flex space-x-4 items-center">
                            <Tooltip title={t(toolTipConstant.shareForm)}>
                                <div
                                    className={`hover:bg-brand-100 p-2.5 h-10 w-10 rounded ${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_SHARE}`}
                                    onClick={(event: any) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        openModal('SHARE_VIEW', {
                                            url: getFormUrl(form, workspace),
                                            title: t(formConstant.shareThisForm)
                                        });
                                    }}
                                >
                                    <Share />
                                </div>
                            </Tooltip>
                            <FormOptionsDropdownMenu className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_OPTIONS} redirectToDashboard={true} form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                        </div>
                    )}
                    {!!group && isAdmin && (
                        <DeleteDropDown
                            onClick={(event) => {
                                event.stopPropagation();
                                event.preventDefault();
                                openModal('DELETE_CONFIRMATION', { title: t(localesCommon.remove) + ' ' + form.title, handleDelete: () => deleteFormFromGroup({ group, workspaceId: workspace.id, form }) });
                            }}
                        />
                    )}
                </div>
            )}
        </div>
    );
}
