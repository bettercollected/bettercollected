import React from 'react';

import DeleteIcon from '@Components/Common/Icons/Delete';
import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import PlusIcon from '@Components/Common/Icons/Plus';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';

interface ConditionalOptionsDropdownProps {
    addOption: any;
    removeOption: any;
}

export default function ConditionalOptionsDropdown({ addOption, removeOption }: ConditionalOptionsDropdownProps) {
    return (
        <>
            <MenuDropdown id="Condition Actions" menuTitle="" showExpandMore={false} menuContent={<EllipsisOption />} width={210}>
                <MenuItem onClick={addOption}>
                    <ListItemIcon>
                        <PlusIcon width={20} height={20} />
                    </ListItemIcon>
                    Add a condition
                </MenuItem>
                <MenuItem onClick={removeOption}>
                    <ListItemIcon>
                        <DeleteIcon />
                    </ListItemIcon>
                    Remove condition
                </MenuItem>
            </MenuDropdown>
        </>
    );
}
