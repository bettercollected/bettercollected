import React from 'react';

import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { ListItemIcon, MenuItem } from '@mui/material';
import { v4 as uuidv4 } from 'uuid';

const FormBuilderActionMenu = ({ id, provided, addBlock, duplicateBlock, deleteBlock, className = '' }: any) => {
    return (
        <div className={`builder-block-actions absolute -top-10 md:top-0 md:-left-1 flex justify-start items-center rounded-sm h-10 w-fit p-[0.5px] bg-white md:bg-transparent mr-4 ${className}`}>
            <MenuDropdown
                showExpandMore={false}
                width={200}
                className="!p-[2px]"
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
                id="block-add-menu"
                hasMenu={false}
                menuTitle="Add a new block"
                menuContent={
                    <div tabIndex={0} className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400" onClick={() => addBlock({ id: uuidv4() })}>
                        <PlusIcon width={40} height={40} />
                    </div>
                }
            ></MenuDropdown>
            <MenuDropdown
                showExpandMore={false}
                width={200}
                className="!p-[2px]"
                onClick={(event: any) => {
                    event.stopPropagation();
                    event.preventDefault();
                }}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 200,
                        overflow: 'hidden',
                        borderRadius: 0,
                        filter: 'drop-shadow(0px 0px 15px rgba(0, 0, 0, 0.15))',
                        mt: 0.5,
                        padding: 0
                    }
                }}
                id="block-options-menu"
                menuTitle="Drag or click to open options for this block"
                menuContent={
                    <div tabIndex={0} className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400" {...provided.dragHandleProps}>
                        <DragHandleIcon width={40} height={40} />
                    </div>
                }
            >
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '50px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={() => duplicateBlock(id)}>
                    <ListItemIcon className="text-inherit">
                        <CopyIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center">Duplicate</span>
                </MenuItem>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '50px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={() => deleteBlock(id)}>
                    <ListItemIcon className="text-inherit">
                        <DeleteIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none">Delete</span>
                </MenuItem>
            </MenuDropdown>
        </div>
    );
};

export default FormBuilderActionMenu;
