import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import CopyIcon from '@Components/Common/Icons/Copy';
import DeleteIcon from '@Components/Common/Icons/Delete';
import DragHandleIcon from '@Components/Common/Icons/DragHandle';
import MuiSwitch from '@Components/Common/Input/Switch';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import IndividualFieldOptions from '@Components/FormBuilder/FieldOptions/IndividualFieldOptions';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import AltRouteIcon from '@mui/icons-material/AltRoute';
import { FormControlLabel, ListItemIcon, MenuItem } from '@mui/material';
import { DraggableProvided } from 'react-beautiful-dnd';

import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { deleteField, selectFormField, updateField } from '@app/store/form-builder/slice';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

interface IFieldOptionsProps {
    provided: DraggableProvided;
    id: string;
}

export default function FieldOptions({ provided, id }: IFieldOptionsProps) {
    const formField: IFormFieldState = useAppSelector(selectFormField(id));
    const dispatch = useAppDispatch();

    const duplicateField = () => {
        const newField: IFormFieldState = { ...formField };
        newField.id = uuidv4();
        dispatch(updateField(newField));
    };
    const deleteFieldWithId = () => {
        dispatch(deleteField(id));
    };

    const handleBlockVisibilityChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();
        const fieldProperties = { ...formField.properties } || {};
        fieldProperties.hidden = checked;
        dispatch(updateField({ ...formField, properties: fieldProperties }));
    };

    const handleFieldRequiredChange = (event: React.SyntheticEvent<Element, Event>, checked: boolean) => {
        event.preventDefault();
        event.stopPropagation();

        const fieldValidations = { ...formField.validations } || {};
        fieldValidations.required = checked;
        dispatch(updateField({ ...formField, validations: fieldValidations }));
    };

    return (
        <MenuDropdown
            showExpandMore={false}
            width={280}
            enterDelay={1000}
            leaveDelay={0}
            closeOnClick={false}
            className="!p-[2px]"
            tabIndex={-1}
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
                <div className="flex items-center h-9 w-9 justify-center cursor-pointer rounded-sm p-1 text-neutral-400" {...provided.dragHandleProps} tabIndex={-1}>
                    <DragHandleIcon tabIndex={-1} width={40} height={40} />
                </div>
            }
        >
            <div className="flex flex-col gap-2 py-3">
                <p className="px-5 text-xs font-semibold tracking-widest leading-none uppercase text-black-700">Options</p>
            </div>

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
                    control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleBlockVisibilityChange} checked={!!formField.properties?.hidden} />}
                />
            </MenuItem>
            {!NonInputFormBuilderTagNames.includes(formField.type || FormBuilderTagNames.LAYOUT_SHORT_TEXT) && (
                <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100">
                    <FormControlLabel
                        slotProps={{
                            typography: {
                                fontSize: 14
                            }
                        }}
                        label="Required"
                        labelPlacement="start"
                        className="m-0 text-xs flex items-center justify-between w-full"
                        control={<MuiSwitch sx={{ m: 1 }} className="text-black-900 m-0" size="small" onChange={handleFieldRequiredChange} checked={!!formField.validations?.required} />}
                    />
                </MenuItem>
            )}

            <IndividualFieldOptions field={formField} />

            <Divider className="my-2" />
            <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={duplicateField}>
                <ListItemIcon className="text-black-900">
                    <AltRouteIcon width={20} height={20} />
                </ListItemIcon>
                <span className="leading-none flex items-center">Add conditional logic</span>
            </MenuItem>
            <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={duplicateField}>
                <ListItemIcon className="text-black-900">
                    <CopyIcon width={20} height={20} />
                </ListItemIcon>
                <span className="leading-none flex items-center justify-between w-full">
                    <span>Duplicate</span>
                    <span className="italic text-xs text-black-500">Ctrl/Cmd + D</span>
                </span>
            </MenuItem>
            <MenuItem sx={{ paddingX: '20px', paddingY: '10px', height: '30px' }} className="flex items-center body4 !text-black-700 hover:bg-brand-100" onClick={deleteFieldWithId}>
                <ListItemIcon className="text-black-900">
                    <DeleteIcon width={20} height={20} />
                </ListItemIcon>
                <span className="leading-none flex items-center justify-between w-full">
                    <span>Delete</span>
                    <span className="italic text-xs text-black-500">Ctrl/Cmd + Shift + D</span>
                </span>
            </MenuItem>
        </MenuDropdown>
    );
}
