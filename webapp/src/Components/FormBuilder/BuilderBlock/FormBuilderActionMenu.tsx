import React from 'react';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import { DeleteOutlined } from '@mui/icons-material';
import { Menu } from '@mui/material';
import { v4 as uuidv4 } from 'uuid';

import { OptionIcon } from '@app/components/icons/option';

const FormBuilderActionMenu = ({ id, provided, addBlock, deleteBlock }: any) => {
    const noOptionsObj = {
        key: 'no-options',
        label: <p className="m-0 p-0">No options available</p>,
        disabled: true
    };

    const optionsMenuItems: any = [
        {
            key: 'delete',
            label: (
                <div aria-hidden onClick={() => deleteBlock({ id })} className="flex items-center justify-center rounded-sm p-1.5 hover:bg-red-500 hover:text-white">
                    <DeleteOutlined />
                    <span className="ml-2">Remove this block</span>
                </div>
            )
        }
    ];

    // TODO: Make menu dropdown working
    // const optionsMenu = <Menu items={optionsMenuItems.length === 0 ? [noOptionsObj] : [...optionsMenuItems]} />;

    return (
        <div className="flex justify-start items-center rounded-sm h-fit w-fit p-[0.5px] mr-3">
            <Tooltip title="Add a new block">
                <div
                    role="button"
                    tabIndex={0}
                    className="flex items-center justify-center rounded-sm mr-0.5 p-1 h-fit text-neutral-400 border-[0.5px] border-transparent border-dashed hover:border-indigo-500 hover:text-indigo-500"
                    onClick={() => deleteBlock(id)}
                >
                    <DeleteOutlined />
                </div>
            </Tooltip>
            <Tooltip title="Add a new block">
                <div
                    role="button"
                    tabIndex={0}
                    className="flex items-center justify-center rounded-sm mr-0.5 p-1 h-fit text-neutral-400 border-[0.5px] border-transparent border-dashed hover:border-indigo-500 hover:text-indigo-500"
                    onClick={() => addBlock({ id: uuidv4() })}
                >
                    <PlusIcon />
                </div>
            </Tooltip>
            {/* <Dropdown trigger={['click']} overlay={optionsMenu} placement="bottomLeft"> */}
            <Tooltip title="Show block options">
                <div tabIndex={0} className="flex items-center justify-center cursor-pointer rounded-sm mr-0.5 p-1 h-fit text-neutral-400 border-[0.5px] border-transparent border-dashed hover:border-orange-500 hover:text-orange-500">
                    <OptionIcon />
                </div>
            </Tooltip>
            {/* </Dropdown> */}
            <Tooltip title="Drag this block">
                <div
                    tabIndex={0}
                    className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400 border-[0.5px] border-transparent border-dashed hover:border-neutral-500 hover:text-neutral-500"
                    {...provided.dragHandleProps}
                >
                    <DragHandleIcon width={40} height={40} />
                </div>
            </Tooltip>
        </div>
    );
};

export default FormBuilderActionMenu;
