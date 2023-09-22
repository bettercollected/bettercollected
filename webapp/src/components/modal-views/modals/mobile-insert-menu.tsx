import {Close} from "@app/components/icons/close";
import {useModal} from "@app/components/modal-views/context";
import Divider from "@Components/Common/DataDisplay/Divider";
import SearchInput from "@Components/Common/Search/SearchInput";
import {useCallback, useEffect, useRef, useState} from "react";
import {BlockTypes, KeyType} from "@app/models/enums/formBuilder";
import {useAppSelector} from "@app/store/hooks";
import {selectActiveFieldId} from "@app/store/form-builder/selectors";
import {
    allowedInputTags, allowedLayoutTags,
    allowedQuestionAndAnswerTags,
    allowedTags
} from "@Components/FormBuilder/BuilderBlock/FormBuilderTagSelector";
import TagListItem from "@Components/FormBuilder/BuilderBlock/TagListItem";
import {List, ListSubheader} from "@mui/material";
import Element from "@Components/Common/Icons/Element";
import ElementsWithLabel from "@Components/Common/Icons/ElementsWithLabel";

export default function MobileInsertMenu() {

    const {closeModal} = useModal()

    const [searchQuery, setSearchQuery] = useState("")


    const [tagList, setTagList] = useState(allowedTags);
    const [selectedTag, setSelectedTag] = useState({blockType: BlockTypes.QUESTION_INPUT_BLOCKS, index: 0});
    const [command, setCommand] = useState('');
    const [blockListTypes, setBlockListTypes] = useState<Array<BlockTypes>>([BlockTypes.QUESTION_INPUT_BLOCKS, BlockTypes.INPUT_BLOCKS, BlockTypes.LAYOUT_BLOCKS]);
    const listRef: any = useRef(null);
    const activeField = useAppSelector(selectActiveFieldId);

    useEffect(() => {
        if (!searchQuery) {
            setBlockListTypes([BlockTypes.QUESTION_INPUT_BLOCKS, BlockTypes.LAYOUT_BLOCKS, BlockTypes.INPUT_BLOCKS]);
            setTagList(allowedTags);
        }
        if (!searchQuery || searchQuery?.includes('\n')) return; // Discard enter character in search query
        const filteredAllowedQuestionAnswerTags = allowedQuestionAndAnswerTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const filteredAllowedInputTags = allowedInputTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const filteredAllowedLayoutTags = allowedLayoutTags.filter((tag) => tag.label.toLocaleLowerCase().includes(searchQuery.toLocaleLowerCase()));
        const newBlockListTypes: Array<BlockTypes> = [];
        let selectedBlockType = BlockTypes.INPUT_BLOCKS;
        if (filteredAllowedQuestionAnswerTags.length > 0) {
            newBlockListTypes.push(BlockTypes.QUESTION_INPUT_BLOCKS);
        }
        if (filteredAllowedLayoutTags.length > 0) {
            newBlockListTypes.push(BlockTypes.LAYOUT_BLOCKS);
        }
        if (filteredAllowedInputTags.length > 0) {
            newBlockListTypes.push(BlockTypes.INPUT_BLOCKS);
        }
        setSelectedTag({blockType: newBlockListTypes.length > 0 ? newBlockListTypes[0] : selectedBlockType, index: 0});
        setTagList([...filteredAllowedQuestionAnswerTags, ...filteredAllowedInputTags, ...filteredAllowedLayoutTags]);
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
                        // handleSelection(tag);
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
                [KeyType.Escape]: () => closeModal(),
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

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [selectedTag, command, getFilteredList, blockListTypes]);

    const scrollToSelectedItem = (blockType: string, index: number | string) => {
        const selectedItem = listRef.current?.querySelector(`[data-id="${blockType}-${index}"]`);
        if (selectedItem) {
            selectedItem.scrollIntoView({behavior: 'smooth', block: 'nearest'});
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
                                            isSelected={isSelected} handleSelection={() => {
                        }}
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


    return (<div className="w-full bg-white rounded-md">
        <div className="px-6 py-4 flex justify-between">
            <span>
                Insert Elements
            </span>
            <div>
                <Close className=" hover:bg-black-100 rounded p-1 !h-6 !w-6" onClick={() => {
                    closeModal()
                }}/>
            </div>
        </div>
        <Divider/>
        <div className='px-6 py-4'>
            <SearchInput className="!bg-black-100 text-black-700" handleSearch={(value) => {
                setSearchQuery(value)
            }}/>
        </div>
        <Divider/>
        <div className="h-[477px]  bg-brand-100 rounded-md overflow-auto">
            <div className="w-full h-full bg-brand-100">
                <List
                    className=""
                    ref={listRef}
                    sx={{
                        width: '100%',
                        position: 'relative',
                        overflow: 'auto',
                        '& ul': {padding: 0}
                    }}
                    subheader={<p/>}
                >
                    {renderAllFields()}
                </List>
            </div>
        </div>
    </div>)
}