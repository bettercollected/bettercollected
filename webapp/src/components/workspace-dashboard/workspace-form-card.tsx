import { PushPin } from '@mui/icons-material';
import { Tooltip } from '@mui/material';

import FormOptionsDropdownMenu from '@app/components/datatable/form/form-options-dropdown';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceFormCardProps {
    form: StandardFormDto;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
    isResponderPortal?: boolean;
    className?: string;
}

export default function WorkspaceFormCard({ form, workspace, hasCustomDomain, isResponderPortal = false, className = '' }: IWorkspaceFormCardProps) {
    const breakpoint = useBreakpoint();

    return (
        <div className={`flex flex-col items-start justify-between h-full bg-white border-[1px] border-black-400 hover:border-brand-500 transition cursor-pointer rounded-[4px] ${className}`}>
            <div className="rounded-[4px] relative w-full px-4 py-6 flex min-h-28 flex-col gap-3 items-start justify-between">
                <div className="rounded-[4px] h-[34px] w-[34px] relative">{form?.settings?.provider === 'typeform' ? <TypeformIcon /> : <GoogleFormIcon className="-ml-2" />}</div>
                <Tooltip title={form?.title || 'Untitled'} arrow placement="top-start" enterDelay={300} enterTouchDelay={0}>
                    <p className="body3 !not-italic leading-none">{['xs', '2xs', 'sm', 'md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title || 'Untitled', 15) : toEndDottedStr(form?.title || 'Untitled', 20)}</p>
                </Tooltip>
                {!isResponderPortal && (
                    <Tooltip className="absolute top-4 right-4" title={form?.settings?.private ? 'Hidden from your public workspace' : 'Public'} arrow placement="bottom-end" enterDelay={300} enterTouchDelay={0}>
                        <p className={`rounded-full leading-none text-[10px] px-2 flex py-1 items-center justify-center ${form?.settings?.private ? 'bg-brand-accent' : 'bg-green-600'} text-white`}>{form?.settings?.private ? 'Hidden' : 'Public'}</p>
                    </Tooltip>
                )}
                {!isResponderPortal && form?.settings?.pinned && (
                    <Tooltip
                        onClick={(e) => e.preventDefault()}
                        className="absolute -top-2 -left-2 bg-white border-[1px] border-black-300 rounded-full p-2"
                        title="Pinned to your public workspace view"
                        arrow
                        placement="top-start"
                        enterDelay={300}
                        enterTouchDelay={0}
                    >
                        <PushPin fontSize="large" className="-rotate-45 text-brand-500" />
                    </Tooltip>
                )}
            </div>
            {!isResponderPortal && (
                <div className="relative flex justify-between items-center p-4 w-full border-t-[1px] border-black-400">
                    <p className="body4 !text-brand-600">{form?.responses} response</p>
                    <FormOptionsDropdownMenu redirectToDashboard={true} className="absolute right-4" form={form} hasCustomDomain={hasCustomDomain} workspace={workspace} />
                </div>
            )}
        </div>
    );
}
