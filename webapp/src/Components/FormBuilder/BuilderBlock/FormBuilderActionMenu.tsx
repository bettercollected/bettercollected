import React from 'react';

import PlusIcon from '@Components/Common/Icons/Plus';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import FieldOptions from '@Components/FormBuilder/FieldOptions/FieldOptions';
import { v4 as uuidv4 } from 'uuid';

const FormBuilderActionMenu = ({ id, provided, addBlock, className = '' }: any) => {
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
            <FieldOptions id={id} provided={provided} />
        </div>
    );
};

export default FormBuilderActionMenu;
