import React, { useEffect, useRef, useState } from 'react';

import _ from 'lodash';

import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { Draggable, DraggableProvided, DraggableStateSnapshot } from 'react-beautiful-dnd';
import ContentEditable from 'react-contenteditable';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addQuestionAndAnswerField, setActiveFieldIndex, setBlockFocus, setIsFormDirty, updateField } from '@app/store/form-builder/slice';
import { useAppAsyncDispatch, useAppDispatch } from '@app/store/hooks';
import { contentEditableClassNames, isContentEditableTag } from '@app/utils/formBuilderBlockUtils';

import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderBlockContent from './FormBuilderBlockContent';
import FormBuilderTagSelector from './FormBuilderTagSelector';

interface IFormBuilderBlockProps {
    item: any;
    position: any;
    addBlock: any;
    duplicateBlock: any;
    onKeyDown?: any;
    deleteBlock: any;
    updateBlock: any;
    fields: any;
}

interface IFormBuilderBlockState {
    htmlBackup: any;
    html: any;
    type: FormBuilderTagNames;
    imageUrl: any;
    placeholder: boolean;
    isTyping: any;
    previousKey: any;
    tagSelectorMenuOpen: boolean;
    actionMenuOpen: boolean;
    isHovering: boolean;
    isFocused: boolean;
}

export default function FormBuilderBlock({ item, position, addBlock, duplicateBlock, deleteBlock, updateBlock, onKeyDown = () => {}, fields }: IFormBuilderBlockProps) {
    const CMD_KEY = '/';
    const contentEditable = useRef(null);

    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();

    const [state, setState] = useState<IFormBuilderBlockState>({
        htmlBackup: null,
        html: item.html || 'Type / to open commands',
        type: item.type || FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        imageUrl: item.imageUrl || '',
        placeholder: true,
        isTyping: false,
        previousKey: null,
        tagSelectorMenuOpen: false,
        actionMenuOpen: false,
        isHovering: false,
        isFocused: false
    });

    useEffect(() => {
        // Add a placeholder if the first block has no sibling elements and no content
        const hasPlaceholder = addPlaceholder({
            content: item.html || item.imageUrl
        });
        if (!hasPlaceholder) {
            setState({
                ...state,
                html: item.html,
                type: item.type,
                imageUrl: item.imageUrl
            });
        }

        return () => {
            document.removeEventListener('click', closeActionMenu, false);
        };
    }, []);

    const addPlaceholder = ({ content }: any) => {
        if (!content) {
            setState({
                ...state,
                html: 'Type / to open commands',
                type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                imageUrl: '',
                placeholder: true,
                isTyping: false
            });
            return true;
        } else {
            return false;
        }
    };

    const openActionMenu = (parent: any, trigger: any) => {
        setState({
            ...state,
            actionMenuOpen: true
        });
        // Add listener asynchronously to avoid conflicts with
        // the double click of the text selection
        setTimeout(() => {
            document.addEventListener('click', closeActionMenu, false);
        }, 100);
    };

    const closeActionMenu = () => {
        setState({
            ...state,
            actionMenuOpen: false
        });
        document.removeEventListener('click', closeActionMenu, false);
    };

    const openTagSelectorMenu = (trigger: any) => {
        setState({
            ...state,
            tagSelectorMenuOpen: true
        });
        document.addEventListener('click', closeTagSelectorMenu, false);
    };

    const closeTagSelectorMenu = () => {
        setState({
            ...state,
            htmlBackup: null,
            tagSelectorMenuOpen: false
        });
        document.removeEventListener('click', closeTagSelectorMenu, false);
    };

    const handleMouseOver = (event: any) => {
        setState((prevState: any) => {
            return {
                ...prevState,
                isFocused: true,
                isHovering: true
            };
        });
        dispatch(setActiveFieldIndex(position));
    };

    const handleMouseOut = () => {
        setState((prevState: any) => {
            return {
                ...prevState,
                isFocused: false,
                isHovering: false
            };
        });

        dispatch(setActiveFieldIndex(-1));
    };

    const dispatchChange = () => {
        dispatch(updateField({ ...item, value: state.html }));
    };

    const handleChange = async (e: any) => {
        const newHtml = e.target.value;
        await asyncDispatch(setIsFormDirty(true));
        setState({ ...state, html: newHtml });
        dispatchChange();
    };

    const handleFocus = () => {
        // If a placeholder is set, we remove it when the block gets focused
        if (state.placeholder) {
            setState({
                ...state,
                html: '',
                placeholder: false,
                isTyping: true
            });
        } else {
            setState({ ...state, isTyping: true });
        }
        dispatch(setActiveFieldIndex(position));
        dispatch(setBlockFocus({ fieldId: item.id, isFocused: true }));
    };

    const handleBlur = () => {
        // Show placeholder if block is still the only one and empty
        const hasPlaceholder = addPlaceholder({
            content: state.html || state.imageUrl
        });
        if (!hasPlaceholder) {
            setState({ ...state, isTyping: false });
        }
        dispatch(setActiveFieldIndex(undefined));
        dispatch(setBlockFocus({ fieldId: item.id, isFocused: false }));
    };

    const handleKeyDown = (event: React.KeyboardEvent) => {
        event.preventDefault();
        if (event.key === CMD_KEY) {
            // If the user starts to enter a command, we store a backup copy of
            // the html. We need this to restore a clean version of the content
            // after the content type selection was finished.
            setState({ ...state, htmlBackup: state.html });
        } else if (event.key === 'Backspace' && !state.html) {
            deleteBlock({ id: item.id });
        } else if (event.key === 'Enter' && state.previousKey !== 'Shift' && !state.tagSelectorMenuOpen) {
            // If the user presses Enter, we want to add a new block
            // Only the Shift-Enter-combination should add a new paragraph,
            // i.e. Shift-Enter acts as the default enter behaviour
            const newBlock: any = {
                id: item.id,
                html: state.html,
                type: state.type,
                imageUrl: state.imageUrl,
                ref: contentEditable.current
            };
            if (state.type === FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE) {
                const id = uuidv4();
                newBlock['choices'] = {
                    [id]: {
                        id: id,
                        value: ''
                    }
                };
            }
            addBlock(newBlock);
        }
        // We need the previousKey to detect a Shift-Enter-combination
        setState({ ...state, previousKey: event.key });

        // if (item.isFocused && !state.tagSelectorMenuOpen) {
        //     onKeyDown(event, state.tagSelectorMenuOpen);
        // }
    };

    // The openTagSelectorMenu function needs to be invoked on key up. Otherwise
    // the calculation of the caret coordinates does not work properly.
    const handleKeyUp = (e: any) => {
        if (e.key === CMD_KEY) {
            openTagSelectorMenu('KEY_CMD');
        }
    };

    const getSelection = (element: any) => {
        let selectionStart = 0;
        let selectionEnd = 0;
        const isSupported = typeof window.getSelection !== 'undefined';
        if (isSupported && typeof window !== 'undefined') {
            const range = window?.getSelection()?.getRangeAt(0);
            if (range) {
                const preSelectionRange = range.cloneRange();
                preSelectionRange.selectNodeContents(element);
                preSelectionRange.setEnd(range.startContainer, range.startOffset);
                selectionStart = preSelectionRange.toString().length;
                selectionEnd = selectionStart + range.toString().length;
            }
        }
        return { selectionStart, selectionEnd };
    };

    const handleMouseUp = () => {
        const block: any = contentEditable.current;
        const { selectionStart, selectionEnd } = getSelection(block);
        if (selectionStart !== selectionEnd) {
            openActionMenu(block, 'TEXT_SELECTION');
        }
    };

    // Convert editableBlock shape based on the chosen tag
    // i.e. img = display <div><input /><img /></div> (input picker is hidden)
    // i.e. every other tag = <ContentEditable /> with its tag and html content
    const handleTagSelection = (type: FormBuilderTagNames) => {
        console.log(type);
        if (type !== FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
            if (type.includes('question')) {
                dispatch(
                    addQuestionAndAnswerField({
                        position: position,
                        id: item.id,
                        type
                    })
                );
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
                const id = uuidv4();
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
            updateBlock(newBlock);
            closeTagSelectorMenu();
        } else {
            if (state.isTyping) {
                // Update the tag and restore the html backup without the command
                setState((prevState) => {
                    closeTagSelectorMenu();
                    return { ...prevState, type: type, html: state.htmlBackup };
                });
            } else {
                setState((prevState) => {
                    closeTagSelectorMenu();
                    return { ...prevState, type: type };
                });
            }
        }
    };

    return (
        <Draggable draggableId={item.id} index={position}>
            {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                <div
                    ref={provided.innerRef}
                    className={`relative flex w-full flex-col ${snapshot.isDragging ? 'bg-brand-100' : 'bg-transparent'}`}
                    onFocus={(event) => handleMouseOver(event)}
                    onBlur={(event: any) => {
                        if (!event.currentTarget.contains(event.relatedTarget)) {
                            handleMouseOut();
                        }
                    }}
                    {...provided.draggableProps}
                >
                    <div className={`builder-block px-5 min-h-[40px] flex items-center md:px-[89px]`}>
                        <FormBuilderActionMenu index={position} id={item.id} provided={provided} addBlock={addBlock} duplicateBlock={duplicateBlock} deleteBlock={deleteBlock} className={state.isFocused ? 'visible' : 'invisible'} />
                        {!isContentEditableTag(item.type) ? (
                            <FormBuilderBlockContent id={`field-${item.id}`} type={item.type} position={position} reference={contentEditable} field={item} />
                        ) : (
                            <div className="flex flex-col w-full relative">
                                <div className={`w-full px-0 flex items-center min-h-[40px]`}>
                                    <ContentEditable
                                        id={`field-${item.id}`}
                                        innerRef={contentEditable}
                                        data-position={position}
                                        data-type={item.type}
                                        html={state.html || ''}
                                        onChange={handleChange}
                                        onFocus={handleFocus}
                                        onBlur={handleBlur}
                                        onKeyDown={handleKeyDown}
                                        onKeyUp={handleKeyUp}
                                        onMouseUp={handleMouseUp}
                                        tagName={item.type}
                                        className={`m-0 p-0 w-full focus-visible:border-0 focus-visible:outline-none ${contentEditableClassNames(state.placeholder, item.type)}`}
                                    />
                                </div>
                                {/*<FormBuilderTagSelector className={state.tagSelectorMenuOpen ? 'visible' : 'invisible'} closeMenu={closeTagSelectorMenu} handleSelection={handleTagSelection} />*/}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </Draggable>
    );
}
