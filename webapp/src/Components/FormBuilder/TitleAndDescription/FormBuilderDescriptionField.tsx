import React, { useEffect, useRef } from 'react';

import dynamic from 'next/dynamic';

import styled from '@emotion/styled';
import katex from 'katex';
import mermaid from 'mermaid';
import { getCodeString } from 'rehype-rewrite';

const MDEditor: any = dynamic((): any => import('@uiw/react-md-editor').then((mod: any) => mod.default), {
    ssr: false,
    loading: () => <div className="h-[200px]" />
});
const MDEditorCommands: any = dynamic((): any => import('@uiw/react-md-editor').then((mod: any) => mod.commands), { ssr: false });

const StyledFormBuilderDescriptionField = styled.div`
    .w-md-editor-text-pre > code::selection {
        background: #9197fe;
        color: white !important;
    }
`;

interface IFormBuilderDescriptionField {
    description: string;
    handleFormDescriptionChange: Function;
}

export default function FormBuilderDescriptionField({ description, handleFormDescriptionChange }: IFormBuilderDescriptionField) {
    const randomid = () => parseInt(String(Math.random() * 1e15), 10).toString(36);

    const getCode: any = (arr = []) =>
        arr
            .map((dt: any) => {
                if (typeof dt === 'string') {
                    return dt;
                }
                if (dt.props && dt.props.children) {
                    return getCode(dt.props.children);
                }
                return false;
            })
            .filter(Boolean)
            .join('');

    const Code = ({ inline, children = [], className, ...props }: any) => {
        const demoid = useRef(`dome${randomid()}`);
        const code = getCode(children);
        const demo = useRef(null);
        useEffect(() => {
            if (demo.current) {
                try {
                    // @ts-ignore
                    const str = mermaid.render(demoid.current, code, () => null, demo.current);
                    // @ts-ignore
                    demo.current.innerHTML = str;
                } catch (error) {
                    // @ts-ignore
                    demo.current.innerHTML = error;
                }
            }
        }, [code, demo]);

        if (typeof code === 'string' && typeof className === 'string' && /^language-mermaid/.test(className.toLocaleLowerCase())) {
            return (
                <code ref={demo}>
                    <code id={demoid.current} style={{ display: 'none' }} />
                </code>
            );
        }

        const txt: string | any = children[0] || '';
        if (inline) {
            if (typeof txt === 'string' && /^\$\$(.*)\$\$/.test(txt)) {
                const html = katex.renderToString(txt.replace(/^\$\$(.*)\$\$/, '$1'), {
                    throwOnError: false
                });
                return <code dangerouslySetInnerHTML={{ __html: html }} />;
            }
            return <code>{txt}</code>;
        }
        const katexcode = props.node && props.node.children ? getCodeString(props.node.children) : txt;
        if (typeof katexcode === 'string' && typeof className === 'string' && /^language-katex/.test(className.toLocaleLowerCase())) {
            const html = katex.renderToString(katexcode, {
                throwOnError: false
            });
            return <code style={{ fontSize: '150%' }} dangerouslySetInnerHTML={{ __html: html }} />;
        }

        return <code className={String(className)}>{children}</code>;
    };

    // TODO: If its in editable mode show it by default but if its in preview mode and no description is provided then hide it
    return (
        <StyledFormBuilderDescriptionField data-color-mode="light">
            <MDEditor
                value={description}
                onChange={handleFormDescriptionChange}
                textareaProps={{ placeholder: 'Form description' }}
                // renderTextarea={(props: any) => <textarea {...props} />}
                previewOptions={{
                    // rehypePlugins: [[rehypeSanitize]],
                    components: {
                        code: (mdprops: any) => <Code className="mermaid" {...mdprops} />
                    }
                }}
                highlightEnable
                defaultTabEnable={false}
                // preview="edit"
                // commands={[MDEditorCommands.codeEdit, MDEditorCommands.codePreview]}
            />
        </StyledFormBuilderDescriptionField>
    );
}
