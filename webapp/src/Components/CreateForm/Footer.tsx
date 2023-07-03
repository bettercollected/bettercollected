import React from 'react';

import Image from 'next/image';

import DeleteIcon from '@Components/Common/Icons/Delete';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import { FieldsMap } from '@Components/CreateForm/AddFieldGrid';
import { SwipeDownAlt } from '@mui/icons-material';
import Switch from '@mui/material/Switch';
import { value } from 'dom7';
import { useDispatch, useSelector } from 'react-redux';

import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { deleteField, setFieldRequired, setFieldType } from '@app/store/form-builder/slice';
import { RootState } from '@app/store/store';

interface FooterProps {
    fieldId: string;
    deletable: boolean;
    type: string;
}

export default function Footer({ fieldId, type }: FooterProps) {
    const dispatch = useDispatch();

    const isRequired = useSelector<RootState, boolean>((state) => !!state.createForm?.fields[fieldId]?.validations?.required);

    const removeField = () => {
        dispatch(deleteField(fieldId));
    };

    const handleChange = () => {
        dispatch(setFieldRequired({ fieldId, required: !isRequired }));
    };

    const menu = (
        <div className="space-y-2 rounded border bg-white p-2">
            {Object.keys(FieldsMap).map((value, index, array) => {
                return (
                    <div
                        key={value}
                        className={'w-full cursor-pointer rounded p-2 hover:bg-lightBackground'}
                        onClick={() => {
                            if (type !== value) dispatch(setFieldType({ fieldId, type: value }));
                        }}
                    >
                        {FieldsMap[value].value}
                    </div>
                );
            })}
        </div>
    );
    return (
        <div className="flex flex-col items-end justify-between space-y-4 md:flex-row md:items-center md:space-y-0">
            <div className={'rounded  border border-black-400 '}>
                <MenuDropdown
                    id="FormFieldSelect"
                    menuTitle={'Select Form Field'}
                    menuContent={
                        <>
                            <div className={'box-shadow flex w-full p-2 min-w-[240px] cursor-pointer items-center justify-between'}>
                                <div className="flex space-x-4">
                                    <span className={'mr-4 flex items-center'}>{FieldsMap[type].icon}</span>
                                    {FieldsMap[type].value}
                                </div>
                            </div>
                        </>
                    }
                >
                    {menu}
                </MenuDropdown>
            </div>
            <div className={'flex items-center space-x-5 divide-x  divide-gray-400'}>
                {
                    <div className={'h-[22px] text-red-600 w-[22px] cursor-pointer'}>
                        <DeleteIcon className="cursor-pointer" onClick={removeField} />
                    </div>
                }
                {type !== QUESTION_TYPE.STATEMENT && (
                    <div className="flex gap-3 pl-5 text-base items-center font-medium">
                        Required
                        <Switch size={'medium'} checked={isRequired} onClick={handleChange} />
                    </div>
                )}
            </div>
        </div>
    );
}
