import { Tooltip } from '@mui/material';

import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import ActiveLink from '@app/components/ui/links/active-link';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IDataTableProviderFormCellProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
}

export default function DataTableProviderFormCell({ workspace, form }: IDataTableProviderFormCellProps) {
    const Icon = form?.settings?.provider === 'google' ? GoogleFormIcon : TypeformIcon;

    const breakpoint = useBreakpoint();

    return (
        <div className="flex items-center body4 justify-start gap-3">
            <Icon width={40} height={40} />{' '}
            <ActiveLink href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`} className="hover:text-brand-600 hover:underline">
                <Tooltip title={form?.title || 'Untitled'} arrow placement="top-start" enterDelay={300} enterTouchDelay={0}>
                    <span>{['xs', '2xs', 'sm', 'md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title || 'Untitled', 15) : toEndDottedStr(form?.title || 'Untitled', 20)}</span>
                </Tooltip>
            </ActiveLink>
        </div>
    );
}
