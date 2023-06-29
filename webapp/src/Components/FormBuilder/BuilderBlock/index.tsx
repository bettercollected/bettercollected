import React from 'react';

import { Draggable } from 'react-beautiful-dnd';
import ContentEditable from 'react-contenteditable';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { contentEditableClassNames, isContentEditableTag } from '@app/utils/formBuilderBlockUtils';

import FormBuilderActionMenu from './FormBuilderActionMenu';
import FormBuilderBlockContent from './FormBuilderBlockContent';
import FormBuilderTagSelector from './FormBuilderTagSelector';

const CMD_KEY = '/';

export default class FormBuilderBlock extends React.Component<any, any> {
    contentEditable: any = React.createRef();
    fileInput: any = null;
    textInput: any = null;

    constructor(props: any) {
        super(props);
        this.state = {
            htmlBackup: null,
            html: 'Type / to open commands',
            tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
            imageUrl: '',
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
            block: this.contentEditable.current,
            position: this.props.position,
            content: this.props.html || this.props.imageUrl
        });
        if (!hasPlaceholder) {
            this.setState({
                ...this.state,
                html: this.props.html,
                tag: this.props.tag,
                imageUrl: this.props.imageUrl
            });
        }
    }

    componentDidUpdate(prevProps: any, prevState: any) {
        // update the page on the server if one of the following is true
        // 1. user stopped typing and the html content has changed & no placeholder set
        // 2. user changed the tag & no placeholder set
        // 3. user changed the image & no placeholder set
        const stoppedTyping = prevState.isTyping && !this.state.isTyping;
        const hasNoPlaceholder = !this.state.placeholder;
        const htmlChanged = this.props.html !== this.state.html;
        const tagChanged = this.props.tag !== this.state.tag;
        const imageChanged = this.props.imageUrl !== this.state.imageUrl;
        if (((stoppedTyping && htmlChanged) || tagChanged || imageChanged) && hasNoPlaceholder) {
            this.props.updateBlock({
                id: this.props.id,
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

    addPlaceholder = ({ block, position, content }: any) => {
        const isFirstBlockWithoutHtml = position === 1 && !content;
        const isFirstBlockWithoutSibling = block && !block.parentElement.nextElementSibling;
        if (isFirstBlockWithoutHtml && isFirstBlockWithoutSibling) {
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

    handleChange = (e: any) => {
        this.setState({ ...this.state, html: e.target.value });
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
            block: this.contentEditable.current,
            position: this.props.position,
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
            this.props.deleteBlock({ id: this.props.id });
        } else if (e.key === 'Enter' && this.state.previousKey !== 'Shift' && !this.state.tagSelectorMenuOpen) {
            // If the user presses Enter, we want to add a new block
            // Only the Shift-Enter-combination should add a new paragraph,
            // i.e. Shift-Enter acts as the default enter behaviour
            e.preventDefault();
            this.props.addBlock({
                id: this.props.id,
                html: this.state.html,
                tag: this.state.tag,
                imageUrl: this.state.imageUrl,
                ref: this.contentEditable.current
            });
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
        if (tag === FormBuilderTagNames.EMBED_IMAGE || tag === FormBuilderTagNames.INPUT_SHORT_TEXT) {
            this.setState({ ...this.state, tag: tag }, () => {
                this.closeTagSelectorMenu();
                // Add new block so that the user can continue writing
                // after adding an image
                this.props.addBlock({
                    id: this.props.id,
                    ref: this.contentEditable.current,
                    html: 'Type / to open commands',
                    tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
                    imageUrl: '',
                    placeholder: true
                });
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
            <Draggable draggableId={this.props.id} index={this.props.position}>
                {(provided: any) => (
                    <div
                        ref={provided.innerRef}
                        className="relative flex w-full flex-col"
                        onFocus={(event) => this.handleMouseOver(event)}
                        onBlur={(event: any) => {
                            if (!event.currentTarget.contains(event.relatedTarget)) {
                                this.handleMouseOut();
                            }
                        }}
                        {...provided.draggableProps}
                    >
                        <div className="flex flex-col md:flex-row w-full">
                            <FormBuilderActionMenu id={this.props.id} provided={provided} addBlock={this.props.addBlock} deleteBlock={this.props.deleteBlock} />
                            {!isContentEditableTag(this.state.tag) ? (
                                <FormBuilderBlockContent tag={this.state.tag} position={this.props.position} reference={this.contentEditable} />
                            ) : (
                                <div className="flex flex-col w-full">
                                    <div className={`mb-4 w-full ${this.state.isFocused ? 'border-b-[1px] border-neutral-200' : 'border-white'} px-0 pb-2 hover:border-indigo-500`}>
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
                                            className={`m-0 p-0 focus-visible:border-0 focus-visible:outline-none ${contentEditableClassNames(this.state.placeholder, this.state.tag)}`}
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
