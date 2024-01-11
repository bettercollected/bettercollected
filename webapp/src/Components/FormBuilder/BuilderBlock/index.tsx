import React, {FocusEvent, FormEvent, KeyboardEvent, useCallback} from 'react';

import FormBuilderBlockContent from '@Components/FormBuilder/BuilderBlock/FormBuilderBlockContent';
import {uuidv4} from '@mswjs/interceptors/lib/utils/uuid';
import {Draggable, DraggableProvided, DraggableStateSnapshot} from 'react-beautiful-dnd';
import {batch} from 'react-redux';
import {v4} from 'uuid';

import {useIsMobile} from '@app/lib/hooks/use-breakpoint';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import {FormBuilderTagNames} from '@app/models/enums/formBuilder';
import {
    resetBuilderMenuState,
    setActiveField,
    setAddNewField,
    setBuilderMenuState,
    setBuilderState, setDeleteField,
    setMoveField,
    setUpdateCommandField
} from '@app/store/form-builder/actions';
import {selectActiveFieldId, selectBuilderState} from '@app/store/form-builder/selectors';
import {IFormFieldState} from '@app/store/form-builder/types';
import {useAppAsyncDispatch, useAppDispatch, useAppSelector} from '@app/store/hooks';
import {isContentEditableTag, isMultipleChoice} from '@app/utils/formBuilderBlockUtils';
import {getLastItem} from '@app/utils/stringUtils';

import CustomContentEditable from '../ContentEditable/CustomContentEditable';
import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderTagSelector from './FormBuilderTagSelector';
import useFormBuilderButtonState from "@Components/FormBuilder/bottomAtom";

interface IBuilderBlockProps {
    item: IFormFieldState;
    draggableId: string | number;
    setBackspaceCount: React.Dispatch<React.SetStateAction<number>>;
}

export default function FormBuilderBlock({item, draggableId, setBackspaceCount}: IBuilderBlockProps) {
    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const lastFieldId = useAppSelector(selectActiveFieldId);
    const {t} = useBuilderTranslation();
    const {setShowButton} = useFormBuilderButtonState();
    const handleTagSelection = (type: FormBuilderTagNames) => {
        batch(() => {
            if (type === FormBuilderTagNames.BUTTON) {
                asyncDispatch(
                    setBuilderState({
                        buttonText: 'Submit'
                    })
                ).then(() => {
                    setShowButton();
                    document.getElementById(`form-builder-button`)?.focus();
                })
                dispatch(setDeleteField(lastFieldId));
                dispatch(resetBuilderMenuState());
            } else {
                const field: IFormFieldState = {
                    id: v4(),
                    type,
                    position: item.position,
                    replace: true
                };
                if (isMultipleChoice(type)) {
                    const choiceId = uuidv4();
                    field.properties = {
                        activeChoiceId: choiceId,
                        activeChoiceIndex: 0,
                        choices: {
                            [choiceId]: {
                                id: choiceId,
                                value: '',
                                position: 0
                            }
                        }
                    };
                }
                dispatch(setAddNewField(field));
                dispatch(resetBuilderMenuState());
                if (isMultipleChoice(type)) {
                    setTimeout(() => document.getElementById(`choice-${field.properties?.activeChoiceId}`)?.focus(), 1);
                } else {
                    setTimeout(() => document.getElementById(`item-${field.id}`)?.focus(), 1);
                }
            }
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
                        dispatch(setMoveField({oldIndex: item.position, newIndex}));
                    }
                }
            });
        },
        [builderState.fields, item.position]
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
        [item.id, item.position, setBackspaceCount]
    );

    const isMobile = useIsMobile();
    const getMarginTop = () => {
        if (item.type === FormBuilderTagNames.LAYOUT_LABEL || item.type === FormBuilderTagNames.CONDITIONAL) return 'mt-5';
        if (item.type === FormBuilderTagNames.LAYOUT_HEADER1 || item.type === FormBuilderTagNames.LAYOUT_HEADER2 || item.type === FormBuilderTagNames.LAYOUT_HEADER3 || item.type === FormBuilderTagNames.LAYOUT_HEADER4) return 'mt-5';
        return '';
    };

    return (
        <Draggable key={item.position} draggableId={draggableId.toString()} index={item.position}>
            {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                <div
                    ref={provided.innerRef}
                    className={`relative  px-12 md:px-[89px] builder-block flex w-full flex-col ${snapshot.isDragging ? 'bg-brand-100' : 'bg-transparent'}   ${getMarginTop()}`}
                    onFocus={(event: FocusEvent<HTMLElement>) => {
                    }}
                    onBlur={(event: FocusEvent<HTMLElement>) => {
                    }}
                    onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => onKeyDownCallback(event, provided)}
                    {...provided.draggableProps}
                >
                    <div
                        className={` min-h-[28px] ${isContentEditableTag(item.type) ? 'mt-5' : '-mt-1'} builder-block flex items-center ${item?.properties?.hidden ? 'opacity-40' : ''}  ${getMarginTop()}`}>
                        <FormBuilderActionMenu index={item.position} id={item.id} provided={provided}
                                               className={!isMobile && builderState.activeFieldIndex !== item.position ? 'invisible' : 'visible'}/>
                        {!isContentEditableTag(item.type) ? (
                            <FormBuilderBlockContent id={`item-${item.id}`} type={item.type} position={item.position}
                                                     field={item}/>
                        ) : (
                            <div className="flex flex-col w-full relative">
                                <div className={`w-full px-0 flex items-center min-h-[24px]`}>
                                    <CustomContentEditable
                                        id={`item-${item.id}`}
                                        tagName={item.type}
                                        type={item.type}
                                        value={item?.value ?? ''}
                                        position={item.position}
                                        showHideHolder={true}
                                        placeholder={item.properties?.placeholder ?? isMobile ? "Click '::' to insert fields" : t('COMPONENTS.COMMON.PLACEHOLDER')}
                                        className="text-[16px] font-medium leading-normal text-black-800"
                                        onBlurCallback={() => {
                                        }}
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
                                                        setBuilderMenuState({
                                                            // isFormDirty: true,

                                                            ...builderState.menus,
                                                            commands: {
                                                                isOpen: false,
                                                                atFieldUuid: '',
                                                                position: 'down'
                                                            }
                                                        })
                                                    );
                                                }
                                                dispatch(
                                                    setUpdateCommandField({
                                                        ...builderState.fields[builderState.activeFieldId],
                                                        value: event.currentTarget.innerText
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
                                        closeMenu={() => {
                                            dispatch(
                                                setBuilderState({
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
                                        }}
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
