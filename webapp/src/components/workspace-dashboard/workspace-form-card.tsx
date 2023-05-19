import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import PinnedIcon from '@Components/Common/Icons/Pinned';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import Share from '@Components/Common/Icons/Share';
import Joyride from '@Components/Joyride';
import { Button, Typography } from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { formsConstant } from '@app/constants/locales/forms';
import { localesGlobal } from '@app/constants/locales/global';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { getFormUrl } from '@app/utils/urlUtils';

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    hasCustomDomain: boolean;
    index?: number;
    workspace?: WorkspaceDto;
    isResponderPortal?: boolean;
    className?: string;
}

export default function WorkspaceFormCard({ form, hasCustomDomain, index, workspace = undefined, isResponderPortal = false, className = '' }: IWorkspaceFormCardProps) {
    const { openModal } = useModal();
    const router = useRouter();

    const { t } = useTranslation();
    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[2px] border-brand-100 hover:border-black-500 transition cursor-pointer rounded-lg shadow-formCard ${className}`}>
            {typeof index !== undefined && index === 0 && environments.ENABLE_JOYRIDE_TOURS && !isResponderPortal && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION}
                    placement="bottom-start"
                    steps={[
                        {
                            title: <span className="sh3">Share your form</span>,
                            content: <p className="body4">You can use this button to share your form to your desired audience.</p>,
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_SHARE}`
                        }
                    ]}
                />
            )}
            <div className="rounded relative w-full px-4 py-6 flex min-h-28 flex-col gap-4 items-start justify-between overflow-hidden">
                <div className="rounded h-[34px] w-[34px]">{form?.settings?.provider === 'typeform' ? <TypeformIcon width={34} height={34} /> : <GoogleFormIcon width={34} height={34} className="-ml-1" />}</div>
                <Tooltip title={form?.title || t(localesGlobal.untitled)}>
                    <Typography className="body3 !leading-none w-[inherit]" noWrap>
                        {form?.title || t(localesGlobal.untitled)}
                    </Typography>
                </Tooltip>
                {!isResponderPortal && (
                    <Tooltip title={form?.settings?.private ? 'Hidden from your public workspace' : t(localesGlobal.public)}>
                        <div className="flex items-center">
                            {form?.settings?.private ? <PrivateIcon /> : <PublicIcon />}
                            <p className={`leading-none text-[10px] text-black-900 ml-2`}>{form?.settings?.private ? t(localesGlobal.hidden) : t(localesGlobal.public)}</p>
                        </div>
                    </Tooltip>
                )}
                {!isResponderPortal && form?.settings?.pinned && (
                    <Tooltip onClick={(e: any) => e.preventDefault()} className="absolute top-2 right-2 bg-white " title="Pinned to your public workspace view">
                        <PinnedIcon />
                    </Tooltip>
                )}
            </div>
            {!isResponderPortal && !!workspace && (
                <div className="relative flex justify-between items-center py-2 px-4 gap-4 w-full border-t-[1px] border-black-400">
                    <Button className="p-2 capitalize hover:bg-brand-100" variant="text" onClick={() => router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}/responses`)}>
                        <span className="body4">
                            {form?.responses} response{!!form?.responses && form.responses > 1 ? 's' : ''}
                        </span>
                    </Button>
                    <div className="flex space-x-4 items-center">
                        <div
                            className={`hover:bg-brand-100 p-2.5 h-10 w-10 rounded ${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_CARD_NAVIGATION_SHARE}`}
                            onClick={(event: any) => {
                                event.preventDefault();
                                event.stopPropagation();
                                openModal('SHARE_VIEW', {
                                    url: getFormUrl(form, workspace),
                                    title: t(formsConstant.shareThisForm)
                                });
                            }}
                        >
                            <Share />
                        </div>
                        <FormOptionsDropdownMenu redirectToDashboard={true} className="" form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                    </div>
                </div>
            )}
        </div>
    );
}
