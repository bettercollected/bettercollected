import React from 'react';

import _ from 'lodash';

import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { Draggable, DraggableProvided, DraggableStateSnapshot } from 'react-beautiful-dnd';
import ContentEditable from 'react-contenteditable';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField } from '@app/store/form-builder/slice';
import { contentEditableClassNames, isContentEditableTag } from '@app/utils/formBuilderBlockUtils';

import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderBlockContent from './FormBuilderBlockContent';
import FormBuilderTagSelector from './FormBuilderTagSelector';

const CMD_KEY = '/';

interface IFormBuilderBlockProps {
    field: any;
    position: any;
    dispatch: any;
    addBlock: any;
    duplicateBlock: any;
    deleteBlock: any;
    updateBlock: any;
}

export default class FormBuilderBlock extends React.Component<IFormBuilderBlockProps, any> {
    contentEditable: any = React.createRef();

    constructor(props: IFormBuilderBlockProps) {
        super(props);
        this.state = {
            htmlBackup: null,
            html: props.field.html || 'Type / to open commands',
            tag: this.props.field.tag || FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            imageUrl: props.field.imageUrl || '',
            placeholder: true,
            isTyping: false,
            previousKey: null,
            tagSelectorMenuOpen: false,
            actionMenuOpen: false,
            isHovering: false,
            isFocused: false
        };
    }

    componentDidMount() {
        // Add a placeholder if the first block has no sibling elements and no content
        const hasPlaceholder = this.addPlaceholder({
            content: this.props.field.html || this.props.field.imageUrl
        });
        if (!hasPlaceholder) {
            this.setState({
                ...this.state,
                html: this.props.field.html,
                tag: this.props.field.tag,
                imageUrl: this.props.field.imageUrl
            });
        }
    }

    componentDidUpdate(prevProps: IFormBuilderBlockProps, prevState: any) {
        // update the page on the server if one of the following is true
        // 1. user stopped typing and the html content has changed & no placeholder set
        // 2. user changed the tag & no placeholder set
        // 3. user changed the image & no placeholder set
        const stoppedTyping = prevState.isTyping && !this.state.isTyping;
        const hasNoPlaceholder = !this.state.placeholder;
        const htmlChanged = this.props.field.html !== this.state.html;
        const tagChanged = this.props.field.tag !== this.state.tag;
        const imageChanged = this.props.field.imageUrl !== this.state.imageUrl;
        if (((stoppedTyping && htmlChanged) || tagChanged || imageChanged) && hasNoPlaceholder) {
            this.props.updateBlock({
                id: this.props.field.id,
                html: this.state.html,
                tag: this.state.tag,
                imageUrl: this.state.imageUrl
            });
        }
    }

    componentWillUnmount() {
        // In case, the user deleted the block, we need to cleanup all listeners
        document.removeEventListener('click', this.closeActionMenu, false);
    }

    addPlaceholder = ({ content }: any) => {
        if (!content) {
            this.setState({
                ...this.state,
                html: 'Type / to open commands',
                tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                imageUrl: '',
                placeholder: true,
                isTyping: false
            });
            return true;
        } else {
            return false;
        }
    };

    handleMouseOver = (event: any) => {
        this.setState((prevState: any) => {
            return {
                isFocused: true,
                isHovering: true
            };
        });
    };

    handleMouseOut = () => {
        this.setState((prevState: any) => {
            return {
                isFocused: false,
                isHovering: false
            };
        });
    };

    dispatchChange = () => {
        this.props.dispatch(addField({ ...this.props.field, value: this.state.html }));
    };

    handleChange = (e: any) => {
        this.setState({ ...this.state, html: e.target.value });
        _.debounce(this.dispatchChange, 500);
    };

    handleFocus = () => {
        // If a placeholder is set, we remove it when the block gets focused
        if (this.state.placeholder) {
            this.setState({
                ...this.state,
                html: '',
                placeholder: false,
                isTyping: true
            });
        } else {
            this.setState({ ...this.state, isTyping: true });
        }
    };

    handleBlur = () => {
        // Show placeholder if block is still the only one and empty
        const hasPlaceholder = this.addPlaceholder({
            content: this.state.html || this.state.imageUrl
        });
        if (!hasPlaceholder) {
            this.setState({ ...this.state, isTyping: false });
        }
    };

    handleKeyDown = (e: any) => {
        if (e.key === CMD_KEY) {
            // If the user starts to enter a command, we store a backup copy of
            // the html. We need this to restore a clean version of the content
            // after the content type selection was finished.
            this.setState({ htmlBackup: this.state.html });
        } else if (e.key === 'Backspace' && !this.state.html) {
            this.props.deleteBlock({ id: this.props.field.id });
        } else if (e.key === 'Enter' && this.state.previousKey !== 'Shift' && !this.state.tagSelectorMenuOpen) {
            // If the user presses Enter, we want to add a new block
            // Only the Shift-Enter-combination should add a new paragraph,
            // i.e. Shift-Enter acts as the default enter behaviour
            e.preventDefault();
            const newBlock: any = {
                id: this.props.field.id,
                html: this.state.html,
                tag: this.state.tag,
                imageUrl: this.state.imageUrl,
                ref: this.contentEditable.current
            };
            if (this.state.tag === FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE) {
                const id = uuidv4();
                newBlock['choices'] = {
                    [id]: {
                        id: id,
                        value: ''
                    }
                };
            }
            this.props.addBlock(newBlock);
        }
        // We need the previousKey to detect a Shift-Enter-combination
        this.setState({ previousKey: e.key });
    };

    // The openTagSelectorMenu function needs to be invoked on key up. Otherwise
    // the calculation of the caret coordinates does not work properly.
    handleKeyUp = (e: any) => {
        if (e.key === CMD_KEY) {
            this.openTagSelectorMenu('KEY_CMD');
        }
    };

    getSelection = (element: any) => {
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

    handleMouseUp = () => {
        const block: any = this.contentEditable.current;
        const { selectionStart, selectionEnd } = this.getSelection(block);
        if (selectionStart !== selectionEnd) {
            this.openActionMenu(block, 'TEXT_SELECTION');
        }
    };

    openActionMenu = (parent: any, trigger: any) => {
        this.setState({
            ...this.state,
            actionMenuOpen: true
        });
        // Add listener asynchronously to avoid conflicts with
        // the double click of the text selection
        setTimeout(() => {
            document.addEventListener('click', this.closeActionMenu, false);
        }, 100);
    };

    closeActionMenu = () => {
        this.setState({
            ...this.state,
            actionMenuOpen: false
        });
        document.removeEventListener('click', this.closeActionMenu, false);
    };

    openTagSelectorMenu = (trigger: any) => {
        this.setState({
            ...this.state,
            tagSelectorMenuOpen: true
        });
        document.addEventListener('click', this.closeTagSelectorMenu, false);
    };

    closeTagSelectorMenu = () => {
        this.setState({
            ...this.state,
            htmlBackup: null,
            tagSelectorMenuOpen: false
        });
        document.removeEventListener('click', this.closeTagSelectorMenu, false);
    };

    // Convert editableBlock shape based on the chosen tag
    // i.e. img = display <div><input /><img /></div> (input picker is hidden)
    // i.e. every other tag = <ContentEditable /> with its tag and html content
    handleTagSelection = (tag: any) => {
        if (tag !== FormBuilderTagNames.LAYOUT_SHORT_TEXT) {
            this.setState({ ...this.state, tag: tag }, () => {
                this.closeTagSelectorMenu();
                // Add new block so that the user can continue writing
                // after adding an image

                const newBlock: any = {
                    id: this.props.field.id,
                    html: this.state.html,
                    tag: this.state.tag,
                    imageUrl: this.state.imageUrl,
                    ref: this.contentEditable.current
                };
                if (this.state.tag === FormBuilderTagNames.QUESTION_RATING) {
                    newBlock['properties'] = {
                        steps: 5
                    };
                }
                if (
                    this.state.tag === FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE ||
                    this.state.tag === FormBuilderTagNames.QUESTION_CHECKBOXES ||
                    this.state.tag === FormBuilderTagNames.QUESTION_RANKING ||
                    this.state.tag === FormBuilderTagNames.QUESTION_DROPDOWN ||
                    this.state.tag === FormBuilderTagNames.QUESTION_MULTISELECT
                ) {
                    const id = uuidv4();
                    newBlock['choices'] = {
                        [id]: {
                            id: id,
                            value: ''
                        }
                    };
                    if (this.state.tag === FormBuilderTagNames.QUESTION_CHECKBOXES || this.state.tag === FormBuilderTagNames.QUESTION_MULTISELECT) {
                        newBlock['properties'] = {
                            allowMultipleSelection: true
                        };
                    }
                }
                this.props.updateBlock(newBlock);
            });
        } else {
            if (this.state.isTyping) {
                // Update the tag and restore the html backup without the command
                this.setState({ tag: tag, html: this.state.htmlBackup }, () => {
                    this.closeTagSelectorMenu();
                });
            } else {
                this.setState({ ...this.state, tag: tag }, () => {
                    this.closeTagSelectorMenu();
                });
            }
        }
    };

    render(): React.ReactNode {
        return (
            <Draggable draggableId={this.props.field.id} index={this.props.position}>
                {(provided: DraggableProvided, snapshot: DraggableStateSnapshot) => (
                    <div
                        ref={provided.innerRef}
                        className={`relative flex w-full flex-col ${snapshot.isDragging ? 'bg-brand-100' : 'bg-transparent'}`}
                        onFocus={(event) => this.handleMouseOver(event)}
                        onBlur={(event: any) => {
                            if (!event.currentTarget.contains(event.relatedTarget)) {
                                this.handleMouseOut();
                            }
                        }}
                        {...provided.draggableProps}
                    >
                        <div className={`builder-block px-5 min-h-[40px] flex items-center md:px-[89px]`}>
                            <FormBuilderActionMenu
                                id={this.props.field.id}
                                provided={provided}
                                addBlock={this.props.addBlock}
                                duplicateBlock={this.props.duplicateBlock}
                                deleteBlock={this.props.deleteBlock}
                                className={this.state.isFocused ? 'visible' : 'invisible'}
                            />
                            {!isContentEditableTag(this.state.tag) ? (
                                <FormBuilderBlockContent tag={this.state.tag} position={this.props.position} reference={this.contentEditable} field={this.props.field} />
                            ) : (
                                <div className="flex flex-col w-full relative">
                                    <div className={`w-full px-0 flex items-center min-h-[40px]`}>
                                        <ContentEditable
                                            innerRef={this.contentEditable}
                                            data-position={this.props.position}
                                            data-tag={this.state.tag}
                                            html={this.state.html}
                                            onChange={this.handleChange}
                                            onFocus={this.handleFocus}
                                            onBlur={this.handleBlur}
                                            onKeyDown={this.handleKeyDown}
                                            onKeyUp={this.handleKeyUp}
                                            onMouseUp={this.handleMouseUp}
                                            tagName={this.state.tag}
                                            className={`m-0 p-0 w-full focus-visible:border-0 focus-visible:outline-none ${contentEditableClassNames(this.state.placeholder, this.state.tag)}`}
                                        />
                                    </div>
                                    {this.state.tagSelectorMenuOpen && <FormBuilderTagSelector closeMenu={this.closeTagSelectorMenu} handleSelection={this.handleTagSelection} />}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </Draggable>
        );
    }
}
