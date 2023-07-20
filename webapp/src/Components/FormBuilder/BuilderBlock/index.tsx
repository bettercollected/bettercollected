import React, { FocusEvent, FormEvent, useEffect } from 'react';

import {
    DragDropContext,
    DragStart,
    DragUpdate,
    Draggable,
    DraggableProvided,
    DraggableStateSnapshot,
    DropResult,
    DroppableProvided,
    DroppableStateSnapshot,
    OnDragEndResponder,
    OnDragStartResponder,
    OnDragUpdateResponder,
    ResponderProvided
} from 'react-beautiful-dnd';
import { batch } from 'react-redux';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setAddNewField, setBuilderState } from '@app/store/form-builder/actions';
import { setFields } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { reorder } from '@app/utils/arrayUtils';

import CustomContentEditable from '../ContentEditable/CustomContentEditable';
import { StrictModeDroppable } from '../StrictModeDroppable';
import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderTagSelector from './FormBuilderTagSelector';

interface IBuilderBlockProps {
    positionOffset?: number;
    droppableClassName?: string;
}

export default function FormBuilderBlock({ positionOffset = 0, droppableClassName = '' }: IBuilderBlockProps) {
    const dispatch = useAppDispatch();
    const builderState = useAppSelector(selectBuilderState);

    const onDragStartHandler: OnDragStartResponder = (start: DragStart, provided: ResponderProvided) => {};

    const onDragUpdateHandler: OnDragUpdateResponder = (update: DragUpdate, provided: ResponderProvided) => {};

    const onDragEndHandler: OnDragEndResponder = (result: DropResult, provided: ResponderProvided) => {
        if (!result.destination || !result.source) return;
        const items: Array<IFormFieldState> = reorder(Object.values(builderState.fields), result.source.index - positionOffset, result.destination.index - positionOffset);

        dispatch(setFields(items));
    };

    useEffect(() => {
        if (Object.values(builderState.fields).length === 0) {
            const newField: IFormFieldState = {
                id: v4(),
                type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                isCommandMenuOpen: false,
                position: Object.values(builderState.fields).length === 0 ? 0 : Object.values(builderState.fields).length + 1
            };
            dispatch(setAddNewField(newField));
        }
    }, []);

    return (
        <DragDropContext onDragStart={onDragStartHandler} onDragUpdate={onDragUpdateHandler} onDragEnd={onDragEndHandler}>
            <StrictModeDroppable droppableId="form-builder">
                {(provided: DroppableProvided, snapshot: DroppableStateSnapshot) => (
                    <div className={`flex flex-col gap-2 transition-all duration-200 ease-in ${snapshot.isDraggingOver ? 'bg-black-100 bg-opacity-30 rounded' : 'bg-white'} ${droppableClassName}`} {...provided.droppableProps} ref={provided.innerRef}>
                        {Object.values(builderState.fields).map((field: IFormFieldState, idx: number) => {
                            const index = idx + positionOffset;
                            return (
                                <Draggable key={index} draggableId={idx.toString()} index={idx}>
                                    {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                                        <div
                                            ref={provided.innerRef}
                                            className={`relative flex w-full flex-col ${snapshot.isDragging ? 'bg-brand-100' : 'bg-transparent'}`}
                                            onFocus={(event: FocusEvent<HTMLElement>) => {
                                                // console.log(event);
                                            }}
                                            onBlur={(event: FocusEvent<HTMLElement>) => {
                                                if (!event.currentTarget.contains(event.relatedTarget)) {
                                                    // console.log(event);
                                                }
                                            }}
                                            {...provided.draggableProps}
                                        >
                                            <div className={`builder-block px-5 min-h-[40px] flex items-center md:px-[89px]`}>
                                                <FormBuilderActionMenu
                                                    index={index}
                                                    id={field.id}
                                                    provided={provided}
                                                    addBlock={() => {}}
                                                    duplicateBlock={() => {}}
                                                    deleteBlock={() => {}}
                                                    className={builderState.activeFieldIndex === index ? 'visible' : 'invisible'}
                                                />
                                                {/* {!isContentEditableTag(field.type) ? (
                                                <FormBuilderBlockContent id={`field-${field.id}`} type={field.type} position={idx} reference={contentEditable} field={field} />
                                            ) : ( */}
                                                <div className="flex flex-col w-full relative">
                                                    <div className={`w-full px-0 flex items-center min-h-[40px]`}>
                                                        <CustomContentEditable
                                                            id={field.id}
                                                            tagName={field.type}
                                                            type={field.type}
                                                            value={field?.label ?? ''}
                                                            position={index}
                                                            activeFieldIndex={builderState.activeFieldIndex}
                                                            placeholder={field.properties?.placeholder ?? 'Type / to open the commands menu'}
                                                            className="text-base text-black-800"
                                                            onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                                                // @ts-ignore
                                                                dispatch(setBuilderState({ isFormDirty: true, fields: { ...builderState.fields, [field.id]: { ...field, label: event.target.value } } }));
                                                            }}
                                                            onKeyUpCallback={(event: React.KeyboardEvent<HTMLElement>) => {
                                                                console.log(field?.label, field?.label?.endsWith('/'));

                                                                if (event.key === 'Escape' || (event.key === 'Backspace' && field?.label?.endsWith('/'))) {
                                                                    event.preventDefault();
                                                                    dispatch(setBuilderState({ isFormDirty: true, menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '' } } }));
                                                                }
                                                                if (builderState.menus?.commands?.isOpen) return;
                                                                if (event.key === 'Enter' && !event.shiftKey) {
                                                                    const newField: IFormFieldState = {
                                                                        id: v4(),
                                                                        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                                                                        isCommandMenuOpen: false,
                                                                        position: idx
                                                                    };
                                                                    batch(() => {
                                                                        dispatch(setAddNewField(newField));
                                                                        dispatch(setBuilderState({ isFormDirty: true, activeFieldIndex: index + 1 }));
                                                                    });
                                                                }
                                                                if (event.key === 'ArrowDown' || event.key === 'Tab') {
                                                                    // TODO: add support for activeFieldIndex increase if there are no elements
                                                                    // TODO: add support for delete key and backspace key
                                                                    event.preventDefault();

                                                                    dispatch(setBuilderState({ activeFieldIndex: index + 1 }));
                                                                }
                                                                if (event.key === 'ArrowUp' || (event.shiftKey && event.key === 'Tab')) {
                                                                    dispatch(setBuilderState({ activeFieldIndex: index - 1 }));
                                                                }
                                                                if (event.code === 'Slash') {
                                                                    dispatch(setBuilderState({ isFormDirty: true, menus: { ...builderState.menus, commands: { isOpen: true, atFieldUuid: field.id } } }));
                                                                }
                                                                if (event.key === 'Backspace') {
                                                                    // TODO: remove the label and if clicked the backspace on empty label delete the field
                                                                    dispatch(setBuilderState({ isFormDirty: true }));
                                                                }
                                                            }}
                                                            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                                                event.preventDefault();
                                                                dispatch(setBuilderState({ activeFieldIndex: index }));
                                                            }}
                                                            onBlurCallback={(event: React.FocusEvent<HTMLElement>) => {
                                                                event.preventDefault();
                                                                dispatch(setBuilderState({ menus: { ...builderState.menus, commands: { isOpen: false, atFieldUuid: '' } } }));
                                                            }}
                                                        />
                                                    </div>
                                                    <FormBuilderTagSelector
                                                        className={!!builderState.menus?.commands?.isOpen && builderState.menus?.commands?.atFieldUuid === field.id ? 'visible' : 'invisible'}
                                                        closeMenu={() => {}}
                                                        handleSelection={() => {}}
                                                    />
                                                </div>
                                                {/* )} */}
                                            </div>
                                        </div>
                                    )}
                                </Draggable>
                            );
                        })}

                        {provided.placeholder}
                    </div>
                )}
            </StrictModeDroppable>
        </DragDropContext>
    );
}
