import { useEffect, useRef, useState } from 'react';

import DeleteIcon from '@Components/Common/Icons/Delete';
import { AlternateEmail, ArrowDownward, ArrowDropDown, DateRange, Grid4x4, Notes, Phone, ShortText, Star, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import LinkIcon from '@mui/icons-material/Link';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { Divider, List, ListItem, ListItemText, ListSubheader, Paper } from '@mui/material';

import { TagIcon } from '@app/components/icons/tag-icon';
import { BlockTypes, FormBuilderTagNames, KeyType } from '@app/models/enums/formBuilder';

const allowedTags = [
    {
        id: FormBuilderTagNames.INPUT_SHORT_TEXT,
        tag: FormBuilderTagNames.INPUT_SHORT_TEXT,
        label: 'Short Input Text',
        icon: <ShortText width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LONG_TEXT,
        tag: FormBuilderTagNames.INPUT_LONG_TEXT,
        label: 'Long Text Input',
        icon: <Notes width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_EMAIL,
        tag: FormBuilderTagNames.INPUT_EMAIL,
        label: 'Email',
        icon: <AlternateEmail width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_NUMBER,
        tag: FormBuilderTagNames.INPUT_NUMBER,
        label: 'Number',
        icon: <TagIcon width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LINK,
        tag: FormBuilderTagNames.INPUT_LINK,
        label: 'Link',
        icon: <LinkIcon width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DATE,
        tag: FormBuilderTagNames.INPUT_DATE,
        label: 'Date',
        icon: <DateRange width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        tag: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        label: 'Phone Number',
        icon: <Phone width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_CHECKBOXES,
        tag: FormBuilderTagNames.INPUT_CHECKBOXES,
        label: 'Checkboxes',
        icon: <CheckBoxOutlineBlankIcon width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        tag: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        label: 'Multiple Choice',
        icon: <RadioButtonUncheckedIcon width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DROPDOWN,
        tag: FormBuilderTagNames.INPUT_DROPDOWN,
        label: 'Dropdown',
        icon: <ArrowDropDown width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_RATING,
        tag: FormBuilderTagNames.INPUT_RATING,
        label: 'Rating',
        icon: <Star width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_RANKING,
        tag: FormBuilderTagNames.INPUT_RANKING,
        label: 'Ranking',
        icon: <TrendingUpSharp width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MATRIX,
        tag: FormBuilderTagNames.INPUT_MATRIX,
        label: 'Matrix',
        icon: <Grid4x4 width={20} height={20} />,
        type: BlockTypes.INPUT_BLOCKS
    },

    {
        id: FormBuilderTagNames.QUESTION_SHORT_TEXT,
        tag: FormBuilderTagNames.QUESTION_SHORT_TEXT,
        label: 'Header + Short Input Text',
        icon: <ShortText width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_LONG_TEXT,
        tag: FormBuilderTagNames.QUESTION_LONG_TEXT,
        label: 'Header + Long Text Input',
        icon: <Notes width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_EMAIL,
        tag: FormBuilderTagNames.QUESTION_EMAIL,
        label: 'Header + Email',
        icon: <AlternateEmail width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_NUMBER,
        tag: FormBuilderTagNames.QUESTION_NUMBER,
        label: 'Header + Number',
        icon: <TagIcon width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_LINK,
        tag: FormBuilderTagNames.QUESTION_LINK,
        label: 'Header + Link',
        icon: <LinkIcon width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_DATE,
        tag: FormBuilderTagNames.QUESTION_DATE,
        label: 'Header + Date',
        icon: <DateRange width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_PHONE_NUMBER,
        tag: FormBuilderTagNames.QUESTION_PHONE_NUMBER,
        label: 'Header + Phone Number',
        icon: <Phone width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_CHECKBOXES,
        tag: FormBuilderTagNames.QUESTION_CHECKBOXES,
        label: 'Header + Checkboxes',
        icon: <CheckBoxOutlineBlankIcon width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE,
        tag: FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE,
        label: 'Header + Multiple Choice',
        icon: <RadioButtonUncheckedIcon width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_DROPDOWN,
        tag: FormBuilderTagNames.QUESTION_DROPDOWN,
        label: 'Header + Dropdown',
        icon: <ArrowDropDown width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_RATING,
        tag: FormBuilderTagNames.QUESTION_RATING,
        label: 'Header + Rating',
        icon: <Star width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.QUESTION_RANKING,
        tag: FormBuilderTagNames.QUESTION_RANKING,
        label: 'Header + Ranking',
        icon: <TrendingUpSharp width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },

    {
        id: FormBuilderTagNames.QUESTION_INPUT_MATRIX,
        tag: FormBuilderTagNames.QUESTION_INPUT_MATRIX,
        label: 'Header + Matrix',
        icon: <Grid4x4 width={20} height={20} />,
        type: BlockTypes.QUESTION_INPUT_BLOCKS
    },

    {
        id: FormBuilderTagNames.EMBED_IMAGE,
        tag: FormBuilderTagNames.EMBED_IMAGE,
        label: 'Image',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.EMBED_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER1,
        tag: FormBuilderTagNames.LAYOUT_HEADER1,
        label: 'Heading 1',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER2,
        tag: FormBuilderTagNames.LAYOUT_HEADER2,
        label: 'Heading 2',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER3,
        tag: FormBuilderTagNames.LAYOUT_HEADER3,
        label: 'Heading 3',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER4,
        tag: FormBuilderTagNames.LAYOUT_HEADER4,
        label: 'Heading 4',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER5,
        tag: FormBuilderTagNames.LAYOUT_HEADER5,
        label: 'Heading 5',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        label: 'Text',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_LABEL,
        tag: FormBuilderTagNames.LAYOUT_LABEL,
        label: 'Label',
        icon: <DeleteIcon width={20} height={20} />,
        type: BlockTypes.LAYOUT_BLOCKS
    }
];

const FormBuilderTagSelector = ({ closeMenu, handleSelection }: any) => {
    const [tagList, setTagList] = useState(allowedTags);
    const [selectedTag, setSelectedTag] = useState({ type: BlockTypes.INPUT_BLOCKS, index: 0 });
    const [command, setCommand] = useState('');

    const [blockListTypes, setBlockListTypes] = useState<Array<any>>([BlockTypes.INPUT_BLOCKS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.EMBED_BLOCKS, BlockTypes.QUESTION_INPUT_BLOCKS]);

    const listRef: any = useRef(null);

    useEffect(() => {
        setTagList(allowedTags);
        // const blockList: Array<any> = [];
        // tagList.forEach((tag) => {
        //     if (!blockList.includes(tag.type)) blockList.push(tag.type);
        // });
        // setBlockListTypes([...blockList]);
    }, []);

    useEffect(() => {
        const handleKeyDown = (e: any) => {
            e.preventDefault();

            const keyActions: any = {
                [KeyType.Enter]: () => {
                    const selectedListItem: any = listRef.current?.querySelector('.selected');
                    if (selectedListItem) {
                        const tag = selectedListItem.dataset.tag;
                        handleSelection(tag);
                    }
                },
                [KeyType.ArrowDown]: selectNextTag,
                [KeyType.ArrowUp]: selectPreviousTag,
                [KeyType.Backspace]: () => {
                    setCommand((prevCommand) => {
                        closeMenu();
                        return command.slice(0, -1);
                    });
                },
                [KeyType.Escape]: () => closeMenu(),
                default: () => {}
            };

            const action = keyActions[e.key] || keyActions.default;
            action();
        };

        const selectNextTag = () => {
            if (getFilteredList(selectedTag.type).length - 1 === selectedTag.index) {
                return setSelectedTag(() => {
                    const type = blockListTypes[(blockListTypes.indexOf(selectedTag.type) + 1) % blockListTypes.length];
                    scrollToSelectedItem(type, 0);
                    return { type, index: 0 };
                });
            }
            setSelectedTag((prevTag) => {
                const filteredList = getFilteredList(selectedTag.type);
                const newIndex = (prevTag.index + 1) % filteredList.length;
                scrollToSelectedItem(prevTag.type, newIndex);
                return { ...prevTag, index: newIndex };
            });
        };

        const selectPreviousTag = () => {
            if (selectedTag.index === 0) {
                return setSelectedTag(() => {
                    const type = blockListTypes[(blockListTypes.indexOf(selectedTag.type) - 1 + blockListTypes.length) % blockListTypes.length];
                    const filteredList = getFilteredList(type);
                    const newIndex = filteredList.length - 1;
                    scrollToSelectedItem(type, newIndex);
                    return { type, index: newIndex };
                });
            }
            setSelectedTag((prevTag) => {
                const filteredList = getFilteredList(selectedTag.type);
                const newIndex = (prevTag.index - 1 + filteredList.length) % filteredList.length;
                scrollToSelectedItem(prevTag.type, newIndex);
                return { ...prevTag, index: newIndex };
            });
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [handleSelection, selectedTag, command, closeMenu]);

    const getFilteredList = (type: string) => {
        return tagList.filter((tag) => tag.type === type);
    };

    const scrollToSelectedItem = (type: string, index: number | string) => {
        const selectedItem = listRef.current?.querySelector(`[data-id="${type}-${index}"]`);
        if (selectedItem) {
            selectedItem.scrollIntoView({
                block: 'end',
                inline: 'end'
            });
        }
    };

    const renderSingleTypeTagElements = (type: string, typeTagList: Array<any>) => (
        <li key={type}>
            <ul>
                <ListSubheader className="font-bold tracking-widest shadow-sm">{type.toUpperCase()}</ListSubheader>
                {typeTagList.length === 0 && <p className="m-0 px-4 py-2 text-sm text-neutral-300">No items</p>}
                {typeTagList.map((tag: any, index: number) => {
                    const isSelected = selectedTag.type === type && selectedTag.index === index;
                    const listItemClass = isSelected ? 'bg-indigo-500 text-white selected' : 'text-neutral-700 hover:bg-indigo-400 hover:text-white';

                    return (
                        <ListItem key={index} data-id={`${type}-${index}`} data-tag={tag.tag} className={`flex items-center px-3 py-2 gap-3 last:border-b-0 ${listItemClass}`} role="button" tabIndex={0} onClick={() => handleSelection(tag.tag)}>
                            {tag.icon}
                            <span className="ml-2">{tag.label}</span>
                        </ListItem>
                    );
                })}
            </ul>
        </li>
    );

    return (
        <div className="absolute top-full left-0 right-0 z-[9999] overflow-hidden rounded bg-white drop-shadow-main">
            <Paper style={{ maxHeight: 320, overflowY: 'auto' }}>
                <List
                    ref={listRef}
                    sx={{
                        width: '100%',
                        bgcolor: 'background.paper',
                        position: 'relative',
                        overflow: 'auto',
                        maxHeight: 300,
                        '& ul': { padding: 0 }
                    }}
                    subheader={<li />}
                >
                    {blockListTypes.map((type) => renderSingleTypeTagElements(type, getFilteredList(type)))}
                </List>
            </Paper>
        </div>
    );
};

export default FormBuilderTagSelector;
