import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import Share from '@Components/Common/Icons/Share';
import Joyride from '@Components/Joyride';
import { PushPin } from '@mui/icons-material';
import { MenuItem, Typography } from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
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
    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[1px] border-brand-100 hover:border-brand-500 transition cursor-pointer rounded ${className}`}>
            {/* {typeof index !== undefined && index === 0 && !isResponderPortal && (
                <Joyride
                    id="workspace-admin-dashboard-form-card-navigations"
                    placement="bottom-start"
                    steps={[
                        {
                            title: <span className="sh3">Share your form</span>,
                            content: <p className="body4">You can use this button to share your form to your desired audience.</p>,
                            target: '.workspace-admin-dashboard-form-card-navigations-share'
                        }
                    ]}
                />
            )} */}
            <div className="rounded relative w-full px-4 py-6 flex min-h-28 flex-col gap-4 items-start justify-between overflow-hidden">
                <div className="rounded h-[34px] w-[34px]">{form?.settings?.provider === 'typeform' ? <TypeformIcon width={34} height={34} /> : <GoogleFormIcon width={34} height={34} className="-ml-1" />}</div>
                <Tooltip title={form?.title || 'Untitled'}>
                    <Typography className="body3 !leading-none w-[inherit]" noWrap>
                        {form?.title || 'Untitled'}
                    </Typography>
                </Tooltip>
                {!isResponderPortal && (
                    <Tooltip className="absolute top-4 right-4" title={form?.settings?.private ? 'Hidden from your public workspace' : 'Public'}>
                        <p className={`rounded-full leading-none text-[10px] px-2 flex py-1 items-center justify-center ${form?.settings?.private ? 'bg-brand-accent' : 'bg-green-600'} text-white`}>{form?.settings?.private ? 'Hidden' : 'Public'}</p>
                    </Tooltip>
                )}
                {!isResponderPortal && form?.settings?.pinned && (
                    <Tooltip onClick={(e: any) => e.preventDefault()} className="absolute -top-2 -left-2 bg-white border-[1px] border-black-300 rounded-full p-2" title="Pinned to your public workspace view">
                        <PushPin fontSize="large" className="-rotate-45 text-brand-500" />
                    </Tooltip>
                )}
            </div>
            {!isResponderPortal && !!workspace && (
                <div className="relative flex justify-between items-center p-3 w-full border-t-[1px] border-black-400">
                    <div
                        onClick={(event: any) => {
                            event.preventDefault();
                            event.stopPropagation();
                            router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}/responses`);
                        }}
                        className="h-full"
                    >
                        <MenuItem sx={{ padding: '8px', maxHeight: '40px', borderRadius: '4px' }} className="body4 bg-brand-100 hover:bg-brand-200">
                            <p className="body4 !text-brand-600">
                                {form?.responses} response{!!form?.responses && form.responses > 1 ? 's' : ''}
                            </p>
                        </MenuItem>
                    </div>
                    <div className="flex space-x-4 items-center">
                        <div
                            className="hover:bg-brand-200 p-2.5 h-10 w-10 rounded workspace-admin-dashboard-form-card-navigations-share"
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
