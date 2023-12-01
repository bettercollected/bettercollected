import { useTranslation } from 'next-i18next';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import SmallLogo from '@Components/Common/Icons/Common/SmallLogo';
import { Typography } from '@mui/material';

import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import ActiveLink from '@app/components/ui/links/active-link';
import { localesCommon } from '@app/constants/locales/common';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';

interface IDataTableProviderFormCellProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
}

export default function DataTableProviderFormCell({ workspace, form }: IDataTableProviderFormCellProps) {
    let Icon = SmallLogo;
    if (form?.settings?.provider === 'google') {
        Icon = GoogleFormIcon;
    } else if (form?.settings?.provider === 'typeform') {
        Icon = TypeformIcon;
    }
    const { t } = useTranslation();

    return (
        <ActiveLink href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`} className="w-fit">
            <Tooltip title="">
                <Typography className="flex justify-start items-center gap-3 !body3 !not-italic" noWrap>
                    <span className="w-10 h-10">
                        <Icon width={40} height={40} />
                    </span>
                    {form?.title || t(localesCommon.untitled)}
                </Typography>
            </Tooltip>
        </ActiveLink>
    );
}
