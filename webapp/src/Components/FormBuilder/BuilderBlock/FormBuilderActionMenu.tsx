import React from 'react';

import PlusIcon from '@Components/Common/Icons/Plus';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import FieldOptions from '@Components/FormBuilder/FieldOptions/FieldOptions';
import { useDispatch } from 'react-redux';
import { v4 as uuidv4 } from 'uuid';

import { useModal } from '@app/components/modal-views/context';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addFieldNewImplementation, selectFormBuilderFields, setFields } from '@app/store/form-builder/slice';
import { useAppSelector } from '@app/store/hooks';

const FormBuilderActionMenu = ({ id, provided, addBlock, className = '', index }: any) => {
    const { openModal } = useModal();

    return (
        <div className={`builder-block-actions absolute -top-10 md:top-0 md:-left-1 flex justify-start items-center rounded-sm h-10 w-fit p-[0.5px] bg-white md:bg-transparent mr-4 ${className}`}>
            <div
                className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400"
                onClick={() => {
                    openModal('FORM_BUILDER_ADD_FIELD_VIEW', { index });
                }}
            >
                <PlusIcon width={40} height={40} />
            </div>
            <FieldOptions id={id} provided={provided} />
        </div>
    );
};

export default FormBuilderActionMenu;
