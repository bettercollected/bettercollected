import React, { FocusEvent, FormEvent } from 'react';

import FormBuilderBlockContent from '@Components/FormBuilder/BuilderBlock/FormBuilderBlockContent';
import { Draggable, DraggableProvided, DraggableStateSnapshot } from 'react-beautiful-dnd';
import { batch } from 'react-redux';
import { v4 } from 'uuid';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setBuilderState } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { isContentEditableTag } from '@app/utils/formBuilderBlockUtils';

import CustomContentEditable from '../ContentEditable/CustomContentEditable';
import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderTagSelector from './FormBuilderTagSelector';

interface IBuilderBlockProps {
    item: IFormFieldState;
}

export default function FormBuilderBlock({ item }: IBuilderBlockProps) {
    const dispatch = useAppDispatch();
    const builderState = useAppSelector(selectBuilderState);

    const handleTagSelection = (type: FormBuilderTagNames) => {
        if (type !== FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
            if (type.includes('question')) {
                // TODO: Add this implementation
                // dispatch(
                //     addQuestionAndAnswerField({
                //         position: position,
                //         id: item.id,
                //         type
                //     })
                // );
                return;
            }
            const newBlock: any = {
                id: item.id,
                type: type
            };
            if (type === FormBuilderTagNames.INPUT_RATING) {
                newBlock['properties'] = {
                    steps: 5
                };
            }
            if (
                type === FormBuilderTagNames.INPUT_MULTIPLE_CHOICE ||
                type === FormBuilderTagNames.INPUT_CHECKBOXES ||
                type === FormBuilderTagNames.INPUT_RANKING ||
                type === FormBuilderTagNames.INPUT_DROPDOWN ||
                type === FormBuilderTagNames.INPUT_MULTISELECT
            ) {
                const id = v4();
                newBlock['properties'] = {};
                newBlock['properties']['choices'] = {
                    [id]: {
                        id: id,
                        value: ''
                    }
                };
                if (type === FormBuilderTagNames.INPUT_CHECKBOXES || type === FormBuilderTagNames.INPUT_MULTISELECT) {
                    newBlock['properties'] = {
                        ...(newBlock['properties'] || {}),
                        allowMultipleSelection: true
                    };
                }
            }
            batch(() => {
                // TODO: Update the block
                dispatch(resetBuilderMenuState());
            });
        }
    };

    return (
        <Draggable key={item.id} draggableId={item.id} index={item.position}>
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
                            index={item.position}
                            id={item.id}
                            provided={provided}
                            addBlock={() => {}}
                            duplicateBlock={() => {}}
                            deleteBlock={() => {}}
                            className={builderState.activeFieldIndex === item.position ? 'visible' : 'invisible'}
                        />
                        {!isContentEditableTag(item.type) ? (
                            <FormBuilderBlockContent id={`item-${item.id}`} type={item.type} position={item.position} item={item} />
                        ) : (
                            <div className="flex flex-col w-full relative">
                                <div className={`w-full px-0 flex items-center min-h-[40px]`}>
                                    <CustomContentEditable
                                        id={item.id}
                                        tagName={item.type}
                                        type={item.type}
                                        value={item?.label ?? ''}
                                        position={item.position}
                                        activeFieldIndex={builderState.activeFieldIndex}
                                        placeholder={item.properties?.placeholder ?? 'Type / to open the commands menu'}
                                        className="text-base text-black-800"
                                        onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                            // @ts-ignore
                                            dispatch(
                                                setBuilderState({
                                                    isFormDirty: true,
                                                    fields: {
                                                        ...builderState.fields,
                                                        [item.id]: { ...item, label: event.currentTarget.innerText }
                                                    }
                                                })
                                            );
                                        }}
                                        onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                                            event.preventDefault();
                                            console.log({ id: item.id, position: item.position });
                                            dispatch(setBuilderState({ activeFieldIndex: item.position }));
                                        }}
                                    />
                                </div>
                                <FormBuilderTagSelector className={!!builderState.menus?.commands?.isOpen && builderState.menus?.commands?.atFieldUuid === item.id ? 'visible' : 'invisible'} closeMenu={() => {}} handleSelection={handleTagSelection} />
                            </div>
                        )}
                    </div>
                </div>
            )}
        </Draggable>
    );
}
