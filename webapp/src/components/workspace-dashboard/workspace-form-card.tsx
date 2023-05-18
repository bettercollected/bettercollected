import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import PinnedIcon from '@Components/Common/Icons/Pinned';
import PrivateIcon from '@Components/Common/Icons/Private';
import PublicIcon from '@Components/Common/Icons/Public';
import Share from '@Components/Common/Icons/Share';
import { PushPin } from '@mui/icons-material';
import { Typography } from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import ActiveLink from '@app/components/ui/links/active-link';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { getFormUrl } from '@app/utils/urlUtils';

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    hasCustomDomain: boolean;
    workspace?: WorkspaceDto;
    isResponderPortal?: boolean;
    className?: string;
}

export default function WorkspaceFormCard({ form, hasCustomDomain, workspace = undefined, isResponderPortal = false, className = '' }: IWorkspaceFormCardProps) {
    const { openModal } = useModal();
    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[2px] border-brand-100 hover:border-black-500 transition cursor-pointer rounded-lg shadow-formCard ${className}`}>
            <div className="rounded relative w-full px-4 py-6 flex min-h-28 flex-col gap-4 items-start justify-between overflow-hidden">
                <div className="rounded h-[34px] w-[34px]">{form?.settings?.provider === 'typeform' ? <TypeformIcon width={34} height={34} /> : <GoogleFormIcon width={34} height={34} className="-ml-1" />}</div>
                <Tooltip title={form?.title || 'Untitled'}>
                    <Typography className="body3 !leading-none w-[inherit]" noWrap>
                        {form?.title || 'Untitled'}
                    </Typography>
                </Tooltip>
                {!isResponderPortal && (
                    <Tooltip title={form?.settings?.private ? 'Hidden from your public workspace' : 'Public'}>
                        <div className="flex items-center">
                            {form?.settings?.private ? <PrivateIcon /> : <PublicIcon />}
                            <p className={`leading-none text-[10px] text-black-900 ml-2`}>{form?.settings?.private ? 'Private' : 'Public'}</p>
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
                <div className="relative flex justify-between items-center px-6 p-3 w-full border-t-[1px] border-black-400">
                    <ActiveLink href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}/responses`}>
                        <p className="body4  hover:underline">
                            {form?.responses} response{!!form?.responses && form.responses > 1 ? 's' : ''}
                        </p>
                    </ActiveLink>
                    <div className="flex space-x-4 items-center">
                        <div
                            className="hover:bg-brand-200 p-2.5 rounded"
                            onClick={(event: any) => {
                                event.preventDefault();
                                event.stopPropagation();
                                openModal('SHARE_VIEW', {
                                    url: getFormUrl(form, workspace),
                                    title: 'this form'
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
