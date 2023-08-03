import React from 'react';

import { ReactMarkdown } from 'react-markdown/lib/react-markdown';
import remarkGfm from 'remark-gfm';

interface IMarkdownText {
    text: string;
}
export default function MarkdownText({ text }: IMarkdownText) {
    return (
        <div className="markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
    );
}
