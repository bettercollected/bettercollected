import {useCallback, useEffect, useRef, useState} from 'react';

import CheckboxIcon from '@Components/Common/Icons/FormBuilder/CheckboxIcon';
import DateIcon from '@Components/Common/Icons/FormBuilder/DateIcon';
import DropDownIcon from '@Components/Common/Icons/FormBuilder/DropDownIcon';
import Element from '@Components/Common/Icons/FormBuilder/Element';
import ElementsWithLabel from '@Components/Common/Icons/FormBuilder/ElementsWithLabel';
import EmailIcon from '@Components/Common/Icons/FormBuilder/EmailIcon';
import LongTextIcon from '@Components/Common/Icons/FormBuilder/LongTextIcon';
import MultipleChoiceIcon from '@Components/Common/Icons/FormBuilder/MultipleChoiceIcon';
import PhoneNumberIcon from '@Components/Common/Icons/FormBuilder/PhoneNumberIcon';
import RatingIcon from '@Components/Common/Icons/FormBuilder/RatingIcon';
import ShortTextIcon from '@Components/Common/Icons/FormBuilder/ShortTextIcon';
import UploadIcon from '@Components/Common/Icons/FormBuilder/UploadIcon';
import TagListItem from '@Components/FormBuilder/BuilderBlock/TagListItem';
import {Tag} from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';
import {List, ListSubheader, Paper} from '@mui/material';

import {Logic} from '@app/components/icons/logic';
import {Ranking} from '@app/components/icons/ranking';
import useClickOutsideMenu from '@app/lib/hooks/use-click-outside-menu';
import {BlockTypes, FormBuilderTagNames, KeyType, LabelFormBuilderTagNames} from '@app/models/enums/formBuilder';
import {OnlyClassNameInterface} from '@app/models/interfaces';
import {selectActiveFieldId, selectPreviousField} from '@app/store/form-builder/selectors';
import {useAppSelector} from '@app/store/hooks';
import ButtonIcon from "@Components/Common/Icons/FormBuilder/ButtonIcon";
import {NumberIcon} from "@Components/Common/Icons/FormBuilder/NumberIcon";
import {MarkdownIcon} from "@Components/Common/Icons/FormBuilder/MarkdownIcon";

export const allowedInputTags = [
    {
        id: FormBuilderTagNames.INPUT_SHORT_TEXT,
        type: FormBuilderTagNames.INPUT_SHORT_TEXT,
        label: 'Short Question',
        icon: <ShortTextIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LONG_TEXT,
        type: FormBuilderTagNames.INPUT_LONG_TEXT,
        label: 'Long Question',
        icon: <LongTextIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_EMAIL,
        type: FormBuilderTagNames.INPUT_EMAIL,
        label: 'Email Address',
        icon: <EmailIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_NUMBER,
        type: FormBuilderTagNames.INPUT_NUMBER,
        label: 'Number',
        icon: <NumberIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LINK,
        type: FormBuilderTagNames.INPUT_LINK,
        label: 'Link',
        icon: <LinkIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DATE,
        type: FormBuilderTagNames.INPUT_DATE,
        label: 'Date',
        icon: <DateIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        type: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        label: 'Phone Number',
        icon: <PhoneNumberIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_CHECKBOXES,
        type: FormBuilderTagNames.INPUT_CHECKBOXES,
        label: 'Checkbox',
        icon: <CheckboxIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        type: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        label: 'Multiple Choice',
        icon: <MultipleChoiceIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DROPDOWN,
        type: FormBuilderTagNames.INPUT_DROPDOWN,
        label: 'Dropdown',
        icon: <DropDownIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_RATING,
        type: FormBuilderTagNames.INPUT_RATING,
        label: 'Rating',
        icon: <RatingIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_RANKING,
        type: FormBuilderTagNames.INPUT_RANKING,
        label: 'Ranking',
        icon: <Ranking width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MEDIA,
        type: FormBuilderTagNames.INPUT_MEDIA,
        label: 'Upload Media',
        icon: <UploadIcon width={24} height={24}/>,
        blockType: BlockTypes.INPUT_BLOCKS
    }
];

export const allowedLayoutTags = [
    {
        id: FormBuilderTagNames.LAYOUT_HEADER1,
        type: FormBuilderTagNames.LAYOUT_HEADER1,
        label: 'Heading 1',
        icon: <div className="font-bold text-[16px]">H1</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER2,
        type: FormBuilderTagNames.LAYOUT_HEADER2,
        label: 'Heading 2',
        icon: <div className="font-bold text-[16px]">H2</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER3,
        type: FormBuilderTagNames.LAYOUT_HEADER3,
        label: 'Heading 3',
        icon: <div className="font-bold text-[16px] ">H3</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER4,
        type: FormBuilderTagNames.LAYOUT_HEADER4,
        label: 'Heading 4',
        icon: <div className="font-bold text-[16px] ">H4</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        type: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        label: 'Text',
        icon: <div className="font-bold text-[16px] px-2 ">T</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_LABEL,
        type: FormBuilderTagNames.LAYOUT_LABEL,
        label: 'Label',
        icon: <div className="font-bold text-[16px] px-2 ">L</div>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_MARKDOWN,
        type: FormBuilderTagNames.LAYOUT_MARKDOWN,
        label: 'Markdown',
        icon: <MarkdownIcon width={24} height={24}/>,
        blockType: BlockTypes.LAYOUT_BLOCKS
    }
];

export const allowedQuestionAndAnswerTags = [
    {
        id: FormBuilderTagNames.QUESTION_SHORT_TEXT,
        type: FormBuilderTagNames.QUESTION_SHORT_TEXT,
        label: 'Short Question',
        icon: <ShortTextIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_LONG_TEXT,
        type: FormBuilderTagNames.QUESTION_LONG_TEXT,
        label: 'Long Question',
        icon: <LongTextIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_EMAIL,
        type: FormBuilderTagNames.QUESTION_EMAIL,
        label: 'Email Address',
        icon: <EmailIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_NUMBER,
        type: FormBuilderTagNames.QUESTION_NUMBER,
        label: 'Number',
        icon: <NumberIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_LINK,
        type: FormBuilderTagNames.QUESTION_LINK,
        label: 'Link',
        icon: <LinkIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_DATE,
        type: FormBuilderTagNames.QUESTION_DATE,
        label: 'Date',
        icon: <DateIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_PHONE_NUMBER,
        type: FormBuilderTagNames.QUESTION_PHONE_NUMBER,
        label: 'Phone Number',
        icon: <PhoneNumberIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_CHECKBOXES,
        type: FormBuilderTagNames.QUESTION_CHECKBOXES,
        label: 'Checkbox',
        icon: <CheckboxIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE,
        type: FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE,
        label: 'Multiple Choice',
        icon: <MultipleChoiceIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_DROPDOWN,
        type: FormBuilderTagNames.QUESTION_DROPDOWN,
        label: 'Dropdown',
        icon: <DropDownIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_RATING,
        type: FormBuilderTagNames.QUESTION_RATING,
        label: 'Rating',
        icon: <RatingIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_RANKING,
        type: FormBuilderTagNames.QUESTION_RANKING,
        label: 'Ranking',
        icon: <Ranking width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_INPUT_MEDIA,
        type: FormBuilderTagNames.QUESTION_INPUT_MEDIA,
        label: 'Upload Media',
        icon: <UploadIcon width={24} height={24}/>,
        blockType: BlockTypes.QUESTION_INPUT_BLOCKS
    }
];

export const allowedAdvancedTags = [
    {
        id: FormBuilderTagNames.CONDITIONAL,
        type: FormBuilderTagNames.CONDITIONAL,
        label: 'Conditional',
        icon: <Logic width={24} height={24}/>,
        blockType: BlockTypes.ADVANCED_FIELDS
    },
    {
        id: FormBuilderTagNames.BUTTON,
        type: FormBuilderTagNames.BUTTON,
        label: 'Submit Button',
        icon: <ButtonIcon width={30} height={30}/>,
        blockType: BlockTypes.ADVANCED_FIELDS
    }
];
export const allowedTags = [...allowedQuestionAndAnswerTags, ...allowedLayoutTags, ...allowedInputTags, ...allowedAdvancedTags];

interface IFormBuilderTagSelector extends OnlyClassNameInterface {
    closeMenu: any;
    handleSelection: any;
    position?: 'up' | 'down';
    searchQuery?: string;
}

const FormBuilderTagSelector = ({
                                    closeMenu,
                                    handleSelection,
                                    className,
                                    position = 'down',
                                    searchQuery = ''
                                }: IFormBuilderTagSelector) => {

    const [command, setCommand] = useState('');
    const listRef: any = useRef(null);
    const activeFieldId = useAppSelector(selectActiveFieldId);
    const previousField = useAppSelector(selectPreviousField(activeFieldId));

    const checkIfPreviousFieldIsLabel = () => {
        if (previousField?.type) {
            return LabelFormBuilderTagNames.includes(previousField?.type) || (previousField?.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT)
        }
    }
    const getBlockListTypes = () => {
        if (checkIfPreviousFieldIsLabel()) {
            return [BlockTypes.INPUT_BLOCKS, BlockTypes.ADVANCED_FIELDS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.QUESTION_INPUT_BLOCKS]
        } else {
            return [BlockTypes.QUESTION_INPUT_BLOCKS, BlockTypes.INPUT_BLOCKS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.ADVANCED_FIELDS]
        }
    }
    const [blockListTypes, setBlockListTypes] = useState<Array<BlockTypes>>(getBlockListTypes());

    const allowableTags = checkIfPreviousFieldIsLabel() ? [...allowedInputTags, ...allowedAdvancedTags, ...allowedLayoutTags, ...allowedQuestionAndAnswerTags] : allowedTags
    const [tagList, setTagList] = useState(allowableTags);

    const [selectedTag, setSelectedTag] = useState({
        blockType: checkIfPreviousFieldIsLabel() ? BlockTypes.INPUT_BLOCKS : BlockTypes.QUESTION_INPUT_BLOCKS,
        index: 0
    });


    useClickOutsideMenu('tag-selector');

    useEffect(() => {
        if (!searchQuery) {
            if (checkIfPreviousFieldIsLabel()) {
                setBlockListTypes([BlockTypes.INPUT_BLOCKS, BlockTypes.ADVANCED_FIELDS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.QUESTION_INPUT_BLOCKS]);

            } else {
                setBlockListTypes([BlockTypes.QUESTION_INPUT_BLOCKS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.INPUT_BLOCKS, BlockTypes.ADVANCED_FIELDS]);
            }
            setTagList(allowableTags);
        }
        if (!searchQuery || searchQuery?.includes('\n')) return; // Discard enter character in search query
        const filteredAllowedQuestionAnswerTags = allowedQuestionAndAnswerTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const filteredAllowedInputTags = allowedInputTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const filteredAllowedLayoutTags = allowedLayoutTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const filteredAllowedConditionalTags = allowedAdvancedTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const newBlockListTypes: Array<BlockTypes> = [];
        let selectedBlockType = BlockTypes.INPUT_BLOCKS;
        if (checkIfPreviousFieldIsLabel()) {
            if (filteredAllowedInputTags.length > 0) {
                newBlockListTypes.push(BlockTypes.INPUT_BLOCKS);
            }
            if (filteredAllowedConditionalTags.length > 0) {
                newBlockListTypes.push(BlockTypes.ADVANCED_FIELDS);
            }
            if (filteredAllowedLayoutTags.length > 0) {
                newBlockListTypes.push(BlockTypes.LAYOUT_BLOCKS);
            }
            if (filteredAllowedQuestionAnswerTags.length > 0) {
                newBlockListTypes.push(BlockTypes.QUESTION_INPUT_BLOCKS);
            }
        } else {
            if (filteredAllowedQuestionAnswerTags.length > 0) {
                newBlockListTypes.push(BlockTypes.QUESTION_INPUT_BLOCKS);
            }
            if (filteredAllowedLayoutTags.length > 0) {
                newBlockListTypes.push(BlockTypes.LAYOUT_BLOCKS);
            }
            if (filteredAllowedInputTags.length > 0) {
                newBlockListTypes.push(BlockTypes.INPUT_BLOCKS);
            }
            if (filteredAllowedConditionalTags.length > 0) {
                newBlockListTypes.push(BlockTypes.ADVANCED_FIELDS);
            }
        }
        setSelectedTag({blockType: newBlockListTypes.length > 0 ? newBlockListTypes[0] : selectedBlockType, index: 0});
        setTagList([...filteredAllowedQuestionAnswerTags, ...filteredAllowedInputTags, ...filteredAllowedLayoutTags, ...filteredAllowedConditionalTags]);
        searchQuery && setBlockListTypes([...newBlockListTypes]);
    }, [searchQuery]);

    const getFilteredList = useCallback(
        (blockType: string) => {
            return tagList.filter((tag) => tag.blockType === blockType);
        },
        [tagList]
    );

    useEffect(() => {
        const handleKeyDown = (e: any) => {
            const keyActions: any = {
                [KeyType.Enter]: () => {
                    e.preventDefault();
                    e.stopPropagation();
                    const selectedListItem: any = listRef.current?.querySelector('.selected');
                    if (selectedListItem) {
                        const tag = selectedListItem.dataset.tag;
                        handleSelection(tag);
                    }
                },
                [KeyType.ArrowDown]: () => selectNextTag(e),
                [KeyType.ArrowUp]: () => selectPreviousTag(e),
                [KeyType.Backspace]: () => {
                    setCommand((prevCommand) => {
                        // closeMenu();
                        return command.slice(0, -1);
                    });
                },
                [KeyType.Escape]: () => closeMenu(),
                default: () => {
                }
            };

            const action = keyActions[e.key] || keyActions.default;
            action();
        };

        const selectNextTag = (e: any) => {
            e.preventDefault();
            if (getFilteredList(selectedTag.blockType).length - 1 === selectedTag.index) {
                return setSelectedTag(() => {
                    const blockType = blockListTypes[(blockListTypes.indexOf(selectedTag.blockType) + 1) % blockListTypes.length];
                    scrollToSelectedItem(blockType, 0);
                    return {blockType, index: 0};
                });
            }
            setSelectedTag((prevTag) => {
                const filteredList = getFilteredList(selectedTag.blockType);
                const newIndex = (prevTag.index + 1) % filteredList.length;
                scrollToSelectedItem(prevTag.blockType, newIndex);
                return {...prevTag, index: newIndex};
            });
        };

        const selectPreviousTag = (e: any) => {
            e.preventDefault();
            if (selectedTag.index === 0) {
                return setSelectedTag(() => {
                    const blockType = blockListTypes[(blockListTypes.indexOf(selectedTag.blockType) - 1 + blockListTypes.length) % blockListTypes.length];
                    const filteredList = getFilteredList(blockType);
                    const newIndex = filteredList.length - 1;
                    scrollToSelectedItem(blockType, newIndex);
                    return {blockType, index: newIndex};
                });
            }
            setSelectedTag((prevTag) => {
                const filteredList = getFilteredList(selectedTag.blockType);
                const newIndex = (prevTag.index - 1 + filteredList.length) % filteredList.length;
                scrollToSelectedItem(prevTag.blockType, newIndex);
                return {...prevTag, index: newIndex};
            });
        };

        const handleMouseDown = (e: any) => {
            const tagSelector = document.getElementById('tag-selector');
            const inputElement = document.getElementById(`item-${activeFieldId}`);
            if (!tagSelector?.contains(e.target) && !inputElement?.contains(e.target)) {
                closeMenu();
            } else {
                e.preventDefault();
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        document.addEventListener('mousedown', handleMouseDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.removeEventListener('mousedown', handleMouseDown);
        };
    }, [handleSelection, selectedTag, command, closeMenu, getFilteredList, blockListTypes]);

    const scrollToSelectedItem = (blockType: string, index: number | string) => {
        const selectedItem = listRef.current?.querySelector(`[data-id="${blockType}-${index}"]`);
        if (selectedItem) {
            selectedItem.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        }
    };

    const scrollBlockTypeToTop = (blockType: BlockTypes) => {
        const blockHeading = document.getElementById(blockType);
        if (blockHeading) {
            blockHeading.scrollIntoView({behavior: 'smooth', block: 'start'});
        }
    };

    const renderSingleTypeTagElements = (blockType: BlockTypes, typeTagList: Array<any>) =>
        typeTagList.length != 0 && (
            <li key={blockType}>
                <ul>
                    <div className="font-medium px-6 py-5 bg-brand-100" id={blockType}>
                        {blockType}
                    </div>
                    {typeTagList.map((tag: any, index: number) => {
                        const isSelected = selectedTag.blockType === blockType && selectedTag.index === index;
                        return <TagListItem key={index} tag={tag} index={index} blockType={blockType}
                                            isSelected={isSelected} handleSelection={handleSelection}
                                            setSelectedTag={setSelectedTag}/>;
                    })}
                </ul>
            </li>
        );

    const renderAllFields = () => {
        const fields = blockListTypes.map((type: BlockTypes) => renderSingleTypeTagElements(type, getFilteredList(type)));
        return fields.every((field) => field === false) ?
            <ListSubheader className="font-bold shadow-sm">No Results found</ListSubheader> : fields;
    };

    const getBlockTypeIcon = (type: BlockTypes) => {
        switch (type) {
            case BlockTypes.INPUT_BLOCKS:
                return <Element className={'text-black-800 '}/>;
            case BlockTypes.QUESTION_INPUT_BLOCKS:
                return <ElementsWithLabel className={'text-black-800'}/>;
            case BlockTypes.LAYOUT_BLOCKS:
                return <div
                    className="text-[16px] px-2 text-center items-center leading-6 text-black-800 font-semibold">H</div>;
            case BlockTypes.ADVANCED_FIELDS:
                return <Logic className={'text-black-800'}/>;
        }
    };

    return (
        <div id="tag-selector"
             className={`absolute max-w-[389px] ${position === 'down' ? 'top-full' : 'bottom-[40px]'} shadow-2xl left-0 right-0 z-[9999] overflow-hidden rounded bg-white drop-shadow-main ${className}`}>
            <Paper style={{maxHeight: 300, maxWidth: 389, width: 'full', overflowY: 'auto'}}>
                <div className="flex h-full">
                    <div className=" py-3">
                        {blockListTypes.map((type: BlockTypes) => (
                            <div
                                key={type}
                                className={`cursor-pointer ${selectedTag.blockType === type ? 'bg-brand-200' : ''} px-4 py-2 `}
                                onClick={() => {
                                    setSelectedTag({blockType: type, index: 0});
                                    scrollBlockTypeToTop(type);
                                }}
                            >
                                {getBlockTypeIcon(type)}
                            </div>
                        ))}
                    </div>
                    <div className="w-full h-full bg-brand-100">
                        <List
                            className=""
                            ref={listRef}
                            sx={{
                                width: '100%',
                                position: 'relative',
                                overflow: 'auto',
                                maxHeight: 300,
                                '& ul': {padding: 0}
                            }}
                            subheader={<p/>}
                        >
                            {renderAllFields()}
                        </List>
                    </div>
                </div>
            </Paper>
        </div>
    );
};

export default FormBuilderTagSelector;
