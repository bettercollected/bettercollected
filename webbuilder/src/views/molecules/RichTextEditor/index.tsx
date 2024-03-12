import { useState } from 'react';

import Color from '@tiptap/extension-color';
import TextStyle from '@tiptap/extension-text-style';
import Underline from '@tiptap/extension-underline';
import { EditorProvider, useCurrentEditor, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { FontSize } from '@app/utils/richTextEditorExtenstion/fontSize';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { ArrowDown } from '@app/views/atoms/Icons/ArrowDown';

export function getPlaceholderValueForTitle(fieldType: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.EMAIL:
            return 'Enter Your Email Address';
        case FieldTypes.NUMBER:
            return 'Enter Number';
        case FieldTypes.SHORT_TEXT:
            return 'Enter Text';
        case FieldTypes.LINK:
            return 'Enter Link';
        case FieldTypes.PHONE_NUMBER:
            return 'Enter Your Phone Number';
        case FieldTypes.FILE_UPLOAD:
            return 'Upload Your File';
        case FieldTypes.YES_NO:
            return 'Are you sure?';
        case FieldTypes.DROP_DOWN:
            return 'Select an option';
        case FieldTypes.MULTIPLE_CHOICE:
            return 'Select from list below.';
        case FieldTypes.TEXT:
            return 'Add Text';
        default:
            return 'No Field Selected';
    }
}

export const Extenstions = [StarterKit, TextStyle, FontSize, Underline, Color];

export function RichTextEditor({
    field,
    onUpdate
}: {
    field: FormField;
    onUpdate: (editor: any) => void;
}) {
    const getContentForEditor = () => {
        return field.title
            ? getHtmlFromJson(field.title ?? '')
            : getPlaceholderValueForTitle(field.type || FieldTypes.SHORT_TEXT);
    };

    return (
        <div className="tiptap group relative">
            <EditorProvider
                content={getContentForEditor()}
                extensions={Extenstions}
                slotBefore={<TiptapMenuBar />}
                editorProps={{ attributes: { class: 'outline-none' } }}
            >
                {''}
            </EditorProvider>
        </div>
    );
}

const TiptapMenuBar = ({ focused }: any) => {
    const editorRef = useCurrentEditor();
    const FontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64];
    const [size, setSize] = useState(5);

    const editor = editorRef.editor;

    if (!editor) {
        return null;
    }

    const handleUpdateFontSize = (value = 0) => {
        setSize((prevSize) => {
            const newSize = prevSize + value;
            editor?.chain().focus().setFontSize(`${FontSizes[newSize]}`).run();
            return newSize;
        });
    };

    return (
        <button
            className={cn(
                `absolute -top-16 mb-2 flex hidden items-center rounded-lg bg-white px-4 py-2 shadow-tooltip`,
                'group-focus-within:flex'
            )}
            tabIndex={0}
            onClick={() => {
                return true;
            }}
        >
            <button
                onClick={() => {
                    console.log('BOlded');

                    editor?.chain().focus().toggleBold().run();
                }}
            >
                <strong className="px-2 text-2xl">B</strong>
            </button>
            <button onClick={() => editor?.chain().focus().toggleItalic().run()}>
                <em className="px-2 text-2xl">I</em>
            </button>
            <button onClick={() => editor?.chain().focus().toggleUnderline().run()}>
                <u className="px-2 text-2xl">U</u>
            </button>
            {/* <button
                        onClick={() => {
                            setShowColorPicker(true);
                            editor?.chain().focus().setColor(color).run();
                        }}
                    >
                        <u className="text-2xl">A</u>
                    </button>
                    {showColorPicker && (
                        <HexColorPicker
                            color={color}
                            onChange={(newColor) => {
                                setColor(newColor);
                                setShowColorPicker(false);
                            }}
                            className="z-100 absolute"
                        />
                    )} */}
            <button
                onClick={() => editor?.chain().focus().undo().run()}
                disabled={!editor.can().undo()}
                className="!px-2 disabled:cursor-not-allowed disabled:text-black-900/60"
            >
                Undo
            </button>
            <button
                onClick={() => editor?.chain().focus().redo().run()}
                disabled={!editor.can().redo()}
                className="!px-2 disabled:cursor-not-allowed disabled:text-black-900/60"
            >
                Redo
            </button>
            <div className="flex flex-row items-center justify-center gap-2">
                <span>{FontSizes[size]}</span>
                <div className="flex flex-col">
                    <button
                        onClick={() => {
                            handleUpdateFontSize(+1);
                        }}
                    >
                        <ArrowDown className="h-4 w-4 rotate-180" />
                    </button>
                    <button
                        onClick={() => {
                            handleUpdateFontSize(-1);
                        }}
                    >
                        <ArrowDown className="h-4 w-4" />
                    </button>
                </div>
            </div>
        </button>
    );
};
