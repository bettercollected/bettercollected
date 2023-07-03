import { useEffect, useState } from 'react';

import DeleteIcon from '@Components/Common/Icons/Delete';
import { AlternateEmail, ArrowDownward, ArrowDropDown, DateRange, Grid4x4, Notes, Phone, ShortText, Star, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import LinkIcon from '@mui/icons-material/Link';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import { Divider } from '@mui/material';

import { TagIcon } from '@app/components/icons/tag-icon';
import { BlockTypes, FormBuilderTagNames, KeyType } from '@app/models/enums/formBuilder';

const allowedTags = [
    {
        id: FormBuilderTagNames.INPUT_SHORT_TEXT,
        tag: FormBuilderTagNames.INPUT_SHORT_TEXT,
        label: 'Short Input Text',
        icon: <ShortText />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LONG_TEXT,
        tag: FormBuilderTagNames.INPUT_LONG_TEXT,
        label: 'Long Text Input',
        icon: <Notes />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_EMAIL,
        tag: FormBuilderTagNames.INPUT_EMAIL,
        label: 'Email',
        icon: <AlternateEmail />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_NUMBER,
        tag: FormBuilderTagNames.INPUT_NUMBER,
        label: 'Number',
        icon: <TagIcon />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LINK,
        tag: FormBuilderTagNames.INPUT_LINK,
        label: 'Link',
        icon: <LinkIcon />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DATE,
        tag: FormBuilderTagNames.INPUT_DATE,
        label: 'Date',
        icon: <DateRange />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        tag: FormBuilderTagNames.INPUT_PHONE_NUMBER,
        label: 'Phone Number',
        icon: <Phone />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_CHECKBOXES,
        tag: FormBuilderTagNames.INPUT_CHECKBOXES,
        label: 'Checkboxes',
        icon: <CheckBoxOutlineBlankIcon />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        tag: FormBuilderTagNames.INPUT_MULTIPLE_CHOICE,
        label: 'Multiple Choice',
        icon: <RadioButtonUncheckedIcon />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_DROPDOWN,
        tag: FormBuilderTagNames.INPUT_DROPDOWN,
        label: 'Dropdown',
        icon: <ArrowDropDown />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_LINEAR_SCALE,
        tag: FormBuilderTagNames.INPUT_LINEAR_SCALE,
        label: 'Linear Scale',
        icon: <Star />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_RANKING,
        tag: FormBuilderTagNames.INPUT_RANKING,
        label: 'Ranking',
        icon: <TrendingUpSharp />,
        type: BlockTypes.INPUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.INPUT_MATRIX,
        tag: FormBuilderTagNames.INPUT_MATRIX,
        label: 'Matrix',
        icon: <Grid4x4 />,
        type: BlockTypes.INPUT_BLOCKS
    },

    {
        id: FormBuilderTagNames.EMBED_IMAGE,
        tag: FormBuilderTagNames.EMBED_IMAGE,
        label: 'Image',
        icon: <DeleteIcon />,
        type: BlockTypes.EMBED_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER1,
        tag: FormBuilderTagNames.LAYOUT_HEADER1,
        label: 'Heading 1',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER2,
        tag: FormBuilderTagNames.LAYOUT_HEADER2,
        label: 'Heading 2',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER3,
        tag: FormBuilderTagNames.LAYOUT_HEADER3,
        label: 'Heading 3',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER4,
        tag: FormBuilderTagNames.LAYOUT_HEADER4,
        label: 'Heading 4',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_HEADER5,
        tag: FormBuilderTagNames.LAYOUT_HEADER5,
        label: 'Heading 5',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        tag: FormBuilderTagNames.LAYOUT_SHORT_TEXT,
        label: 'Text',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    },
    {
        id: FormBuilderTagNames.LAYOUT_LABEL,
        tag: FormBuilderTagNames.LAYOUT_LABEL,
        label: 'Label',
        icon: <DeleteIcon />,
        type: BlockTypes.LAYOUT_BLOCKS
    }
];

const FormBuilderTagSelector = ({ closeMenu, handleSelection }: any) => {
    const [tagList, setTagList] = useState(allowedTags);
    const [selectedTag, setSelectedTag] = useState(0);
    const [command, setCommand] = useState('');

    const layoutBlocksTagList = tagList.filter((lst) => lst.type === BlockTypes.LAYOUT_BLOCKS);
    const inputBlocksTagList = tagList.filter((lst) => lst.type === BlockTypes.INPUT_BLOCKS);
    const embedBlocksTagList = tagList.filter((lst) => lst.type === BlockTypes.EMBED_BLOCKS);
    const questionsBlocksTagList = tagList.filter((lst) => lst.type === BlockTypes.QUESTION_BLOCKS);

    // Filter tagList based on given command
    useEffect(() => {
        setTagList(allowedTags);
    }, [command]);

    // Attach listener to allow tag selection via keyboard
    useEffect(() => {
        const handleKeyDown = (e: any) => {
            e.preventDefault();
            switch (e.key) {
                case KeyType.Enter: {
                    handleSelection(tagList[selectedTag].tag);
                    break;
                }

                case KeyType.ArrowDown:
                case KeyType.Tab: {
                    const newSelectedTag = selectedTag === tagList.length - 1 ? 0 : selectedTag + 1;
                    setSelectedTag(newSelectedTag);
                    break;
                }

                case KeyType.ArrowUp: {
                    const newSelectedTag = selectedTag === 0 ? tagList.length - 1 : selectedTag - 1;
                    setSelectedTag(newSelectedTag);
                    break;
                }

                case KeyType.Backspace: {
                    if (command) {
                        setCommand(command.slice(0, -1));
                    } else {
                        closeMenu();
                    }
                    break;
                }
                default: {
                    // setCommand(command + e.key);
                }
            }
        };
        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [tagList, selectedTag, handleSelection, command, closeMenu]);

    const renderSingleTypeTagElements = (type: string, typeTagList: Array<any>) => (
        <div className="items-center">
            <p className="mb-0 px-3 py-2 font-bold tracking-widest">{type.toUpperCase()}</p>
            {typeTagList.length === 0 && <p className="m-0 px-3 py-2 text-neutral-300">No items</p>}
            {typeTagList.map((tag, key) => {
                return (
                    <div
                        key={key}
                        data-tag={tag.tag}
                        className={`${tagList.indexOf(tag) === selectedTag ? 'bg-indigo-500 text-white' : 'text-neutral-700 hover:bg-indigo-400 hover:text-white'} flex items-center px-3 py-2 last:border-b-0`}
                        role="button"
                        tabIndex={0}
                        onClick={() => handleSelection(tag.tag)}
                    >
                        {tag.icon}
                        <span className="ml-2">{tag.label}</span>
                    </div>
                );
            })}
        </div>
    );

    return (
        <div className="absolute top-full left-0 right-0 z-[9999] overflow-hidden rounded bg-white shadow-custom-box-shadow3">
            <div className="h-60 overflow-auto">
                {renderSingleTypeTagElements(BlockTypes.INPUT_BLOCKS, inputBlocksTagList)}
                <Divider style={{ margin: 0 }} />
                {renderSingleTypeTagElements(BlockTypes.LAYOUT_BLOCKS, layoutBlocksTagList)}
                <Divider style={{ margin: 0 }} />
                {renderSingleTypeTagElements(BlockTypes.EMBED_BLOCKS, embedBlocksTagList)}
                <Divider style={{ margin: 0 }} />
                {renderSingleTypeTagElements(BlockTypes.QUESTION_BLOCKS, questionsBlocksTagList)}
            </div>
        </div>
    );
};

export default FormBuilderTagSelector;
