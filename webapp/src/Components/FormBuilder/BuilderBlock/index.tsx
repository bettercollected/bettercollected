import React, { FocusEvent, FormEvent, KeyboardEvent, useCallback } from 'react';

import FormBuilderBlockContent from '@Components/FormBuilder/BuilderBlock/FormBuilderBlockContent';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { Popover } from '@mui/material';
import { Draggable, DraggableProvided, DraggableStateSnapshot } from 'react-beautiful-dnd';
import { batch } from 'react-redux';
import { v4 } from 'uuid';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setActiveField, setAddNewField, setBuilderState, setCommandMenuPosition, setMoveField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { isContentEditableTag } from '@app/utils/formBuilderBlockUtils';
import { getLastItem } from '@app/utils/stringUtils';

import CustomContentEditable from '../ContentEditable/CustomContentEditable';
import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderTagSelector from './FormBuilderTagSelector';

interface IBuilderBlockProps {
    item: IFormFieldState;
    draggableId: string | number;
    setBackspaceCount: React.Dispatch<React.SetStateAction<number>>;
}

export default function FormBuilderBlock({ item, draggableId, setBackspaceCount }: IBuilderBlockProps) {
    const dispatch = useAppDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const { t } = useBuilderTranslation();

    const handleTagSelection = (type: FormBuilderTagNames) => {
        batch(() => {
            const field = {
                id: v4(),
                type,
                position: item.position,
                replace: true
            };
            dispatch(setAddNewField(field));
            dispatch(resetBuilderMenuState());
        });
    };

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent<HTMLDivElement>, provided: DraggableProvided) => {
            batch(() => {
                if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();

                    const direction = event.key === 'ArrowDown' ? 1 : -1;
                    const newIndex = item.position + direction;

                    if (newIndex >= 0 && newIndex < Object.keys(builderState.fields).length) {
                        dispatch(setMoveField({ oldIndex: item.position, newIndex }));
                    }
                }
            });
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [builderState, item.position]
    );

    const onFocusCallback = useCallback(
        (event: React.FocusEvent<HTMLElement>) => {
            setBackspaceCount(0);
            dispatch(
                setActiveField({
                    position: item.position,
                    id: item.id
                })
            );
        },
        [dispatch, item.id, item.position, setBackspaceCount]
    );

    const getMarginTop = (type: FormBuilderTagNames) => {
        if (NonInputFormBuilderTagNames.includes(type)) {
            return 'mt-3';
        }
    };

    return (
        <Draggable key={item.position} draggableId={draggableId.toString()} index={item.position}>
            {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                <div
                    ref={provided.innerRef}
                    className={`relative flex w-full flex-col ${snapshot.isDragging ? 'bg-brand-100' : 'bg-transparent'}`}
                    onFocus={(event: FocusEvent<HTMLElement>) => {}}
                    onBlur={(event: FocusEvent<HTMLElement>) => {}}
                    onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => onKeyDownCallback(event, provided)}
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
                            <FormBuilderBlockContent id={`item-${item.id}`} type={item.type} position={item.position} field={item} />
                        ) : (
                            <div className="flex flex-col w-full relative">
                                <div className={`w-full px-0 flex items-center min-h-[40px]`}>
                                    <CustomContentEditable
                                        id={item.id}
                                        tagName={item.type}
                                        type={item.type}
                                        value={item?.value ?? ''}
                                        position={item.position}
                                        showPlaceHolder={false}
                                        activeFieldIndex={builderState.activeFieldIndex}
                                        placeholder={item.properties?.placeholder ?? t('COMPONENTS.COMMON.PLACEHOLDER')}
                                        className="text-base text-black-800"
                                        onFocusCallback={onFocusCallback}
                                        onKeyDownCallback={(event: KeyboardEvent<HTMLDivElement>) => {
                                            if (builderState?.menus?.commands?.isOpen)
                                                if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
                                                    event.preventDefault();
                                                    event.stopPropagation();
                                                }
                                        }}
                                        onChangeCallback={(event: FormEvent<HTMLElement>) => {
                                            setBackspaceCount(0);
                                            batch(() => {
                                                // @ts-ignore
                                                if (event.nativeEvent.inputType === 'deleteContentBackward' && getLastItem(builderState.fields[builderState.activeFieldId]?.value ?? '') === '/') {
                                                    dispatch(
                                                        setBuilderState({
                                                            isFormDirty: true,
                                                            menus: {
                                                                ...builderState.menus,
                                                                commands: {
                                                                    isOpen: false,
                                                                    atFieldUuid: '',
                                                                    position: 'down'
                                                                }
                                                            }
                                                        })
                                                    );
                                                }
                                                dispatch(
                                                    setBuilderState({
                                                        isFormDirty: true,
                                                        fields: {
                                                            ...builderState.fields,
                                                            [item.id]: { ...item, value: event.currentTarget.innerText }
                                                        }
                                                    })
                                                );
                                            });
                                        }}
                                    />
                                </div>
                                {!!builderState.menus?.commands?.isOpen && builderState.menus?.commands?.atFieldUuid === item.id && (
                                    <FormBuilderTagSelector
                                        className={!!builderState.menus?.commands?.isOpen && builderState.menus?.commands?.atFieldUuid === item.id ? 'visible' : 'invisible'}
                                        position={builderState.menus?.commands?.position}
                                        closeMenu={() => {}}
                                        handleSelection={handleTagSelection}
                                        searchQuery={builderState.fields[builderState.activeFieldId]?.value?.split('/').slice(-1)[0] || ''}
                                    />
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </Draggable>
    );
}
