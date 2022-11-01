import React, { useEffect, useState } from 'react';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Absolute imports
import { toEndDottedStr } from '@app/utils/stringUtils';

type Props = {
    description: string;
    contentStripLength?: number;
    displayShowMore?: boolean;
    markdownClassName?: string;
    textClassName?: string;
};

MarkdownText.defaultProps = {
    contentStripLength: 110,
    displayShowMore: true,
    markdownClassName: '',
    textClassName: ''
};
export default function MarkdownText({ description, contentStripLength = 110, displayShowMore = true, markdownClassName = '', textClassName = '' }: Props) {
    const [showMore, setShowMore] = useState(false);
    const [showDesc, setShowDesc] = useState('');

    useEffect(() => {
        const desc = description || 'No description available for this company.';
        let descStripped = desc;
        if (desc.length > contentStripLength && !showMore && displayShowMore) {
            descStripped = toEndDottedStr(desc, contentStripLength);
        }
        setShowDesc(descStripped);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showMore, description]);

    const source = showDesc.replace(/\\n/gi, '\n');

    return (
        <>
            {description && (
                <>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} className={`m-0 p-0 mark-down-text ${markdownClassName}`}>
                        {source}
                    </ReactMarkdown>
                    {!showMore && displayShowMore && description.length > contentStripLength && (
                        <p aria-hidden className={`show-more-less-text m-0 p-0 cursor-pointer text-blue-500 hover:text-blue-400 ${textClassName}`} onClick={() => setShowMore(!showMore)}>
                            {!showMore ? 'Show more' : 'Show less'}
                        </p>
                    )}
                </>
            )}
            {!description && (
                <p className={`m-0 p-0 ${textClassName}`} style={{ color: '#9b9b9b' }}>
                    {source}
                </p>
            )}
        </>
    );
}
