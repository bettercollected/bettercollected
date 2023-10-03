import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import MuiSwitch from '@Components/Common/Input/Switch';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import FormValidations from '@Components/FormBuilder/FieldOptions/FormValidations';
import StepsOption from '@Components/FormBuilder/FieldOptions/StepsOption';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { FormControlLabel, ListItemIcon, MenuItem } from '@mui/material';
import { DraggableProvided } from 'react-beautiful-dnd';
import { batch } from 'react-redux';

import { useModal } from '@app/components/modal-views/context';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, resetBuilderMenuState, setAddNewField, setDeleteField, setIdentifierField, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState, selectFormField, selectResponseOwnerField } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField } from '@app/utils/formBuilderBlockUtils';

interface IFieldOptionsProps {
    provided: DraggableProvided;
    id: string;
    position: number;
}

export default function FieldOptions({ provided, id, position }: IFieldOptionsProps) {
    const field: IFormFieldState = useAppSelector(selectFormField(id));
    const dispatch = useAppDispatch();
    const responseOwnerField = useAppSelector(selectResponseOwnerField);
    const [open, setOpen] = useState(false);
    const { t } = useBuilderTranslation();
    const builderState = useAppSelector(selectBuilderState);
    const isMobile = useIsMobile();
    const duplicateField = () => {
        const newField: IFormFieldState = { ...field };
        newField.id = uuidv4();
        newField.position = position;
        batch(() => {
            setOpen(false);
            dispatch(addDuplicateField(newField));
        });
    };
    const deleteFieldWithId = () => {
        batch(() => {
            setOpen(false);
            dispatch(setDeleteField(id));
        });
    };

    const { openModal } = useModal();

    const handleSetEmailIdentifier = (event: any, checked: boolean) => {
        if (checked) dispatch(setIdentifierField(field?.id));
        else dispatch(setIdentifierField(''));
    };

    const hasLabelField = () => {
        if (NonInputFormBuilderTagNames.includes(field.type)) return true;
        const previousField: any = Object.values(builderState.fields)[field.position - 1];
        return previousField?.type === FormBuilderTagNames.LAYOUT_LABEL;
    };

    const addFieldLabel = () => {
        dispatch(setAddNewField(createNewField(builderState.activeFieldIndex - 1, FormBuilderTagNames.LAYOUT_LABEL)));
    };

    return (
        <MenuDropdown
            showExpandMore={false}
            width={280}
            enterDelay={1000}
            leaveDelay={0}
            open={open}
            closeOnClick={false}
            className="!p-[0px]"
            tabIndex={-1}
            onClick={(event: React.MouseEvent<HTMLElement>) => {
                event.stopPropagation();
                event.preventDefault();
                setOpen(true);
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
            menuTitle={t('COMPONENTS.OPTIONS.TOOLTIP_TITLE')}
            menuContent={
                <div className={`flex items-center justify-center cursor-pointer rounded-sm text-neutral-400 `} {...provided.dragHandleProps} tabIndex={-1}>
                    <DragHandleIcon className={isMobile && builderState.activeFieldId === id ? 'text-black-800' : ''} tabIndex={-1} width={24} height={24} />
                </div>
            }
        >
            <div
                onKeyDown={(event) => {
                    event.stopPropagation();
                }}
            >
                <div className="flex flex-col gap-2 py-3">
                    <p className="px-5 text-xs font-semibold tracking-widest leading-none uppercase text-black-700">{t('COMPONENTS.OPTIONS.DEFAULT')}</p>
                </div>

                <MenuItem
                    className="md:hidden"
                    onClick={() => {
                        batch(() => {
                            setOpen(false);
                            openModal(isMobile ? 'MOBILE_INSERT_MENU' : 'FORM_BUILDER_ADD_FIELD_VIEW', { index: position });
                        });
                    }}
                >
                    <ListItemIcon className="text-black-900">
                        <PlusIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className=" text-black-700">{t('INSERT.DEFAULT')}</span>
                </MenuItem>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={duplicateField}>
                    <ListItemIcon className="text-black-900">
                        <CopyIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center justify-between w-full">
                        <span>{t('COMPONENTS.ACTIONS.DUPLICATE')}</span>
                        <span className="italic text-xs text-black-500">Ctrl/Cmd + D</span>
                    </span>
                </MenuItem>
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={deleteFieldWithId}>
                    <ListItemIcon className="text-black-900">
                        <DeleteIcon width={20} height={20} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center justify-between w-full">
                        <span>{t('COMPONENTS.ACTIONS.DELETE')}</span>
                        <span className="italic text-xs text-black-500">Ctrl/Cmd + Del</span>
                    </span>
                </MenuItem>

                {field?.type == FormBuilderTagNames.INPUT_EMAIL && (
                    <MenuItem sx={{ paddingX: '20px', paddingY: '10px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100">
                        <FormControlLabel
                            slotProps={{
                                typography: {
                                    fontSize: 14
                                }
                            }}
                            label={t('COMPONENTS.OPTIONS.IDENTIFIER_FIELD')}
                            labelPlacement="start"
                            className="m-0 text-xs flex items-center justify-between w-full"
                            control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleSetEmailIdentifier} checked={responseOwnerField === field?.id} />}
                        />
                    </MenuItem>
                )}

                <StepsOption field={field} />

                {!hasLabelField() && (
                    <>
                        <Divider />
                        <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 xl:hidden hover:bg-brand-100" onClick={addFieldLabel}>
                            <ListItemIcon className=" rounded text-black-900">
                                <span className="bg-black-100 w-5 h-5 text-center justify-center font-bold text-[14px] flex items-center">L</span>
                            </ListItemIcon>
                            <span className="leading-none flex items-center justify-between w-full">
                                <span>{t('COMPONENTS.ACTIONS.ADD_LABEL')}</span>
                                <span className="italic text-xs text-black-500">Alt + L</span>
                            </span>
                        </MenuItem>
                    </>
                )}

                <FormValidations field={field} />
            </div>
        </MenuDropdown>
    );
}
