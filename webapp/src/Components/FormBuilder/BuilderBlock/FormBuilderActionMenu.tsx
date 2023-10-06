import React from 'react';

import DeleteIcon from '@Components/Common/Icons/Delete';
import PlusIcon from '@Components/Common/Icons/Plus';
import FieldOptions from '@Components/FormBuilder/FieldOptions/FieldOptions';

import { useModal } from '@app/components/modal-views/context';
import { resetBuilderMenuState, setDeleteField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppAsyncDispatch, useAppSelector } from '@app/store/hooks';

const FormBuilderActionMenu = ({ id, provided, className = '', index }: any) => {
    const { openModal } = useModal();
    const asyncDispatch = useAppAsyncDispatch();

    const activeField = useAppSelector(selectBuilderState).activeFieldId;

    return (
        <div className={`builder-block-actions flex justify-start items-center min-h-6 rounded-sm w-fit ${id === activeField ? '!text-black-800' : 'text-black-600'}  gap-1 bg-white md:bg-transparent  ${className}`}>
            <div
                className="items-center justify-center cursor-pointer rounded-sm hidden md:flex"
                onClick={() => {
                    asyncDispatch(resetBuilderMenuState()).then(() => {
                        openModal('FORM_BUILDER_ADD_FIELD_VIEW', { index });
                    });
                }}
            >
                <PlusIcon width={24} height={24} />
            </div>
            <DeleteIcon
                className={`hidden cursor-pointer md:block ${id === activeField ? '!text-black-800' : 'text-black-600'}`}
                width={20}
                height={20}
                onClick={() => {
                    asyncDispatch(setDeleteField(id));
                }}
            />
            <FieldOptions id={id} provided={provided} position={index} />
        </div>
    );
};

export default FormBuilderActionMenu;
