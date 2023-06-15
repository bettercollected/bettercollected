import React from 'react';

import { useTranslation } from 'next-i18next';

import Delete from '@Components/Common/Icons/Delete';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { MoreHoriz } from '@mui/icons-material';
import { MenuItem } from '@mui/material';

import { localesCommon } from '@app/constants/locales/common';
import { toolTipConstant } from '@app/constants/locales/tooltip';

export default function DeleteDropDown({ onClick, className, label }: { onClick: (event?: any) => void; className?: string; label?: string }) {
    const { t } = useTranslation();
    return (
        <MenuDropdown
            showExpandMore={false}
            width={200}
            className={className}
            onClick={(event: any) => {
                event.stopPropagation();
                event.preventDefault();
            }}
            PaperProps={{
                elevation: 0,
                sx: {
                    width: 200,
                    overflow: 'hidden',
                    borderRadius: 2,
                    filter: 'drop-shadow(0px 0px 15px rgba(0, 0, 0, 0.15))',
                    mt: 0.5,
                    padding: 0
                }
            }}
            id="language-menu"
            menuTitle={t(toolTipConstant.Options)}
            menuContent={<MoreHoriz />}
        >
            <MenuItem className="body4  flex gap-4" onClick={onClick}>
                <Delete width={20} height={20} />
                {label ?? t(localesCommon.remove)}
            </MenuItem>
        </MenuDropdown>
    );
}
