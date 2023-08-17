import { useRef } from 'react';

import _ from 'lodash';

import { ListItem } from '@mui/material';

import { BlockTypes } from '@app/models/enums/formBuilder';

function TagListItem({ tag, index, blockType, isSelected, handleSelection, setSelectedTag }: { tag: any; index: number; blockType: BlockTypes; isSelected: boolean; handleSelection: any; setSelectedTag: any }): JSX.Element {
    const targetRef = useRef<HTMLDivElement | null>(null);
    const listItemClass = isSelected ? 'bg-brand-200 selected' : '';
    const onMouseMove = () => {
        if (!isSelected) setSelectedTag({ blockType: blockType, index: index });
    };

    return (
        <div ref={targetRef}>
            {/* Your content */}
            <ListItem
                key={index}
                data-id={`${blockType}-${index}`}
                data-tag={tag.type}
                className={`flex items-center px-6 gap-3 body4 text-black-700 last:border-b-0 ${listItemClass}`}
                role="button"
                tabIndex={0}
                onClick={() => {
                    handleSelection(tag.type);
                }}
                onMouseMove={onMouseMove}
            >
                <span className="w-[24px]">{tag.icon}</span>
                <span className="ml-2">{tag.label}</span>
            </ListItem>
        </div>
    );
}

export default TagListItem;
