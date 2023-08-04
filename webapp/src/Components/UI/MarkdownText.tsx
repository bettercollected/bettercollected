import React from 'react';

import { ReactMarkdown } from 'react-markdown/lib/react-markdown';
import remarkGfm from 'remark-gfm';

interface IMarkdownText {
    text: string;
}

const preprocessMarkdown = (text: string) => {
    return text.replace(/^"/gm, '> ').replace(/\n/g, '  \n');
};

const MarkdownText = ({ text }: IMarkdownText) => {
    const processedText = preprocessMarkdown(text);

    return (
        <div>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                className="text-black-900 font-inter space-y-4"
                components={{
                    h1: (props) => <h1 className="text-4xl font-semibold" {...props} />,
                    h2: (props) => <h2 className="text-3xl font-semibold" {...props} />,
                    h3: (props) => <h3 className="text-2xl font-semibold" {...props} />,
                    h4: (props) => <h4 className="text-xl font-semibold" {...props} />,
                    h5: (props) => <h4 className="text-lg font-semibold" {...props} />,
                    p: (props) => <p className="mb-4" {...props} />,
                    code: (props) => <code className="bg-gray-100 p-1 rounded" {...props} />,
                    ul: (props) => <ul className="list-disc pl-6 " {...props} />,
                    ol: (props) => <ol className="list-decimal pl-6 mb-4" {...props} />,
                    li: (props) => <li className="mb-2" {...props} />,
                    input: (props) => <input type="checkbox" className="mr-2" {...props} />,
                    blockquote: (props) => <blockquote className="border-l-4 pl-4 border-gray-300 italic my-4" {...props} />,
                    pre: (props) => <pre className="mb-4" {...props} />
                }}
            >
                {processedText}
            </ReactMarkdown>
        </div>
    );
};

export default MarkdownText;
