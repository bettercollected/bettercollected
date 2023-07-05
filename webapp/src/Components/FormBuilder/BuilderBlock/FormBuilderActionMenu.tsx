import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import AltRouteIcon from '@mui/icons-material/AltRoute';
import { Box, ListItem, ListItemIcon, MenuItem, Switch } from '@mui/material';
import { v4 as uuidv4 } from 'uuid';

const FormBuilderActionMenu = ({ id, provided, addBlock, duplicateBlock, deleteBlock, className = '' }: any) => {
    return (
        <div className={`builder-block-actions absolute -top-10 md:top-0 md:-left-1 flex justify-start items-center rounded-sm h-10 w-fit p-[0.5px] bg-white md:bg-transparent mr-4 ${className}`}>
            <MenuDropdown
                showExpandMore={false}
                width={280}
                enterDelay={1000}
                leaveDelay={0}
                className="!p-[2px]"
                onClick={(event: any) => {
                    event.stopPropagation();
                    event.preventDefault();
                }}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 280,
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
                width={280}
                enterDelay={1000}
                leaveDelay={0}
                className="!p-[2px]"
                onClick={(event: React.MouseEvent<HTMLElement>) => {
                    event.stopPropagation();
                    event.preventDefault();
                }}
                PaperProps={{
                    elevation: 0,
                    sx: {
                        width: 280,
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
                <div className="px-5 py-3">
                    <p className="text-xs font-semibold tracking-widest leading-none uppercase text-black-700">Options</p>
                </div>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100">
                    <ListItem className="flex-1" disableGutters>
                        Hide field
                    </ListItem>
                    <Switch className="text-black-900" />
                </MenuItem>
                <Divider className="my-2" />
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={() => duplicateBlock(id)}>
                    <ListItemIcon className="text-black-900">
                        <AltRouteIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center">Add conditional logic</span>
                </MenuItem>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={() => duplicateBlock(id)}>
                    <ListItemIcon className="text-black-900">
                        <CopyIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center">Duplicate</span>
                </MenuItem>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={() => deleteBlock(id)}>
                    <ListItemIcon className="text-black-900">
                        <DeleteIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none">Delete</span>
                </MenuItem>
            </MenuDropdown>
        </div>
    );
};

export default FormBuilderActionMenu;
