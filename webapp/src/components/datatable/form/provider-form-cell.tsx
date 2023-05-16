import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { Typography } from '@mui/material';

import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import ActiveLink from '@app/components/ui/links/active-link';
import { localesGlobal } from '@app/constants/locales/global';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface IDataTableProviderFormCellProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
}

export default function DataTableProviderFormCell({ workspace, form }: IDataTableProviderFormCellProps) {
    const Icon = form?.settings?.provider === 'google' ? GoogleFormIcon : TypeformIcon;
    const { t } = useTranslation();

    return (
        <ActiveLink href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`} className="w-fit">
            <Tooltip title={form?.title || t(localesGlobal.untitled)}>
                <Typography className="hover:!text-brand-600 hover:!underline flex justify-start items-center gap-3 !body3 !not-italic" noWrap>
                    <span className="w-10 h-10">
                        <Icon width={40} height={40} />
                    </span>
                    {form?.title || t(localesGlobal.untitled)}
                </Typography>
            </Tooltip>
        </ActiveLink>
    );
}
