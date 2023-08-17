import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import MuiSwitch from '@Components/Common/Input/Switch';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import FormValidations from '@Components/FormBuilder/FieldOptions/FormValidations';
import StepsOption from '@Components/FormBuilder/FieldOptions/StepsOption';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { FormControlLabel, ListItemIcon, MenuItem } from '@mui/material';
import { DraggableProvided } from 'react-beautiful-dnd';
import { batch } from 'react-redux';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addDuplicateField, setDeleteField, setIdentifierField, setUpdateField } from '@app/store/form-builder/actions';
import { selectFormField, selectResponseOwnerField } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

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

    const handleBlockVisibilityChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();
        const fieldProperties = { ...field.properties } || {};
        fieldProperties.hidden = checked;
        dispatch(setUpdateField({ ...field, properties: fieldProperties }));
    };

    const handleSetEmailIdentifier = (event: any, checked: boolean) => {
        if (checked) dispatch(setIdentifierField(field?.id));
        else dispatch(setIdentifierField(''));
    };

    return (
        <MenuDropdown
            showExpandMore={false}
            width={280}
            enterDelay={1000}
            leaveDelay={0}
            open={open}
            closeOnClick={false}
            className="!p-[2px]"
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
                <div className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400" {...provided.dragHandleProps} tabIndex={-1}>
                    <DragHandleIcon tabIndex={-1} width={40} height={40} />
                </div>
            }
        >
            <div className="flex flex-col gap-2 py-3">
                <p className="px-5 text-xs font-semibold tracking-widest leading-none uppercase text-black-700">{t('COMPONENTS.OPTIONS.DEFAULT')}</p>
            </div>

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

            <MenuItem sx={{ paddingX: '20px', paddingY: '10px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100">
                <FormControlLabel
                    slotProps={{
                        typography: {
                            fontSize: 14
                        }
                    }}
                    label={t('COMPONENTS.OPTIONS.HIDE_FIELD')}
                    labelPlacement="start"
                    className="m-0 text-xs flex items-center justify-between w-full"
                    control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleBlockVisibilityChange} checked={!!field?.properties?.hidden} />}
                />
            </MenuItem>

            <StepsOption field={field} />

            <FormValidations field={field} />
            <Divider className="my-2" />
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
        </MenuDropdown>
    );
}
