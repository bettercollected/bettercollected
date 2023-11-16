import React, { useState } from 'react';

import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import PlusIcon from '@Components/Common/Icons/Plus';
import MuiSwitch from '@Components/Common/Input/Switch';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import FormValidations from '@Components/FormBuilder/FieldOptions/FormValidations';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { FormControlLabel, ListItemIcon, MenuItem } from '@mui/material';
import { DraggableProvided } from 'react-beautiful-dnd';
import { batch } from 'react-redux';

import { useModal } from '@app/components/modal-views/context';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, LabelFormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, setAddNewField, setDeleteField, setIdentifierField, setUpdateField } from '@app/store/form-builder/actions';
import { selectActiveFieldId, selectFormField, selectNextField, selectPreviousField, selectResponseOwnerField } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField } from '@app/utils/formBuilderBlockUtils';

interface IFieldOptionsProps {
    provided: DraggableProvided;
    id: string;
    position: number;
}

export default function FieldOptions({ provided, id, position }: IFieldOptionsProps) {
    // Hooks
    const { t } = useBuilderTranslation();
    const isMobile = useIsMobile();

    // Redux State
    const field: IFormFieldState = useAppSelector(selectFormField(id));
    const activeFieldId = useAppSelector(selectActiveFieldId);
    const previousField = useAppSelector(selectPreviousField(id));

    // Redux Dispatch
    const dispatch = useAppDispatch();

    // Local State
    const [open, setOpen] = useState(false);

    const nextField = useAppSelector(selectNextField(field.id));

    const isFieldLabel = LabelFormBuilderTagNames.includes(field.type) && nextField?.type?.includes('input_');

    const actualFillField = isFieldLabel ? nextField : field;

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

    const hasLabelField = () => {
        if (NonInputFormBuilderTagNames.includes(field.type)) return true;
        return previousField?.type === FormBuilderTagNames.LAYOUT_LABEL;
    };

    const addFieldLabel = () => {
        dispatch(setAddNewField(createNewField(position - 1, FormBuilderTagNames.LAYOUT_LABEL)));
    };

    const handleBlockVisibilityChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();
        const fieldProperties = { ...field.properties } || {};
        fieldProperties.hidden = checked;
        dispatch(setUpdateField({ ...field, properties: fieldProperties }));
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
                    borderRadius: '8px',
                    boxShadow: '0px 0px 40px 0px rgba(19, 73, 179, 0.25)',
                    mt: 0.5,
                    padding: 0
                }
            }}
            id="block-options-menu"
            menuTitle={t('COMPONENTS.OPTIONS.TOOLTIP_TITLE')}
            menuContent={
                <div className={`flex items-center justify-center cursor-pointer rounded-sm`} {...provided.dragHandleProps} tabIndex={-1}>
                    <DragHandleIcon className={activeFieldId === id ? 'text-black-800' : 'text-black-600'} tabIndex={-1} width={24} height={24} />
                </div>
            }
        >
            <div
                onKeyDown={(event) => {
                    event.stopPropagation();
                }}
            >
                <MenuItem
                    sx={{ paddingX: '16px', paddingY: '6px' }}
                    className="md:hidden"
                    onClick={() => {
                        batch(() => {
                            setOpen(false);
                            openModal(isMobile ? 'MOBILE_INSERT_MENU' : 'FORM_BUILDER_ADD_FIELD_VIEW', { index: position });
                        });
                    }}
                >
                    <ListItemIcon className="text-black-700">
                        <PlusIcon width={24} height={24} />
                    </ListItemIcon>
                    <span className="text-sm text-black-700">{t('INSERT.DEFAULT')}</span>
                </MenuItem>

                <MenuItem sx={{ paddingX: '16px', paddingY: '6px' }} className="flex items-center body4 !text-black-700 " onClick={deleteFieldWithId}>
                    <ListItemIcon className="text-black-00">
                        <DeleteIcon width={24} height={24} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center justify-between w-full">
                        <span className="text-sm">{t('COMPONENTS.ACTIONS.DELETE')}</span>
                        <span className="italic text-xs text-black-500 hidden md:flex">Ctrl/Cmd + Del</span>
                    </span>
                </MenuItem>

                <MenuItem sx={{ paddingX: '16px', paddingY: '6px' }} className="flex items-center body4 !text-black-700 " onClick={duplicateField}>
                    <ListItemIcon className="text-black-700">
                        <CopyIcon width={24} height={24} />
                    </ListItemIcon>
                    <span className="leading-none flex items-center justify-between w-full">
                        <span className="text-sm text-black-700">{t('COMPONENTS.ACTIONS.DUPLICATE')}</span>
                        <span className="italic text-xs text-black-500 hidden md:flex">Ctrl/Cmd + D</span>
                    </span>
                </MenuItem>
                <EmailIdentifier actualIdentifierField={actualFillField} />
                {!hasLabelField() && (
                    <>
                        <MenuItem sx={{ paddingX: '16px', paddingY: '6px' }} className="flex items-center body4 !text-black-700 xl:hidden hover:bg-brand-100" onClick={addFieldLabel}>
                            <ListItemIcon className=" rounded text-black-900">
                                <span className="bg-black-100 w-5 h-5 text-center justify-center font-bold text-[14px] flex items-center">L</span>
                            </ListItemIcon>
                            <span className="leading-none flex items-center justify-between w-full">
                                <span>{t('COMPONENTS.ACTIONS.ADD_LABEL')}</span>
                                <span className="italic text-xs text-black-500 hidden md:flex">Alt + L</span>
                            </span>
                        </MenuItem>
                    </>
                )}
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100">
                    <FormControlLabel
                        slotProps={{
                            typography: {
                                fontSize: 14
                            }
                        }}
                        label="Hide field"
                        labelPlacement="start"
                        className="m-0 text-xs flex items-center justify-between w-full"
                        control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleBlockVisibilityChange} checked={!!field?.properties?.hidden} />}
                    />
                </MenuItem>
                {actualFillField && <FormValidations field={actualFillField} />}
            </div>
        </MenuDropdown>
    );
}

const EmailIdentifier = ({ actualIdentifierField }: { actualIdentifierField?: IFormFieldState }) => {
    const { t } = useBuilderTranslation();

    const dispatch = useAppDispatch();

    const responseOwnerField = useAppSelector(selectResponseOwnerField);

    const handleSetEmailIdentifier = (event: any, checked: boolean) => {
        if (checked) dispatch(setIdentifierField(actualIdentifierField?.id));
        else dispatch(setIdentifierField(''));
    };

    return (
        <>
            {actualIdentifierField?.type === FormBuilderTagNames.INPUT_EMAIL && (
                <MenuItem sx={{ paddingX: '16px', paddingY: '6px' }} className="flex items-center body4 !text-black-700">
                    <FormControlLabel
                        slotProps={{
                            typography: {
                                fontSize: 14
                            }
                        }}
                        label={t('COMPONENTS.OPTIONS.IDENTIFIER_FIELD')}
                        labelPlacement="start"
                        className="m-0 text-xs flex items-center justify-between w-full"
                        control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleSetEmailIdentifier} checked={responseOwnerField === actualIdentifierField?.id} />}
                    />
                </MenuItem>
            )}
        </>
    );
};
