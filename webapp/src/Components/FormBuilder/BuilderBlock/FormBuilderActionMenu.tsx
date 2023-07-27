import React from 'react';

import PlusIcon from '@Components/Common/Icons/Plus';
import FieldOptions from '@Components/FormBuilder/FieldOptions/FieldOptions';

import { useModal } from '@app/components/modal-views/context';
import { resetBuilderMenuState } from '@app/store/form-builder/actions';
import { useAppAsyncDispatch } from '@app/store/hooks';

const FormBuilderActionMenu = ({ id, provided, className = '', index }: any) => {
    const { openModal } = useModal();
    const asyncDispatch = useAppAsyncDispatch();

    return (
        <div className={`builder-block-actions absolute -top-10 md:top-0 md:-left-1 flex justify-start items-center rounded-sm h-10 w-fit p-[0.5px] bg-white md:bg-transparent mr-4 ${className}`}>
            <div
                className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400"
                onClick={() => {
                    asyncDispatch(resetBuilderMenuState()).then(() => {
                        openModal('FORM_BUILDER_ADD_FIELD_VIEW', { index });
                    });
                }}
            >
                <PlusIcon width={40} height={40} />
            </div>
            <FieldOptions id={id} provided={provided} position={index} />
        </div>
    );
};

export default FormBuilderActionMenu;
