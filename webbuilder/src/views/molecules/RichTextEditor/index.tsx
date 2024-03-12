import { useCallback, useState } from 'react';

import Color from '@tiptap/extension-color';
import TextStyle from '@tiptap/extension-text-style';
import Underline from '@tiptap/extension-underline';
import { Transaction } from '@tiptap/pm/state';
import {
    BubbleMenu,
    Editor,
    EditorContent,
    generateHTML,
    useEditor
} from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
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
    const FontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64];
    const [size, setSize] = useState(5);

    const getContentForEditor = () => {
        return field.title
            ? getHtmlFromJson(field.title ?? '')
            : getPlaceholderValueForTitle(field.type || FieldTypes.SHORT_TEXT);
    };
    const editor = useEditor({
        extensions: Extenstions,
        content: getContentForEditor(),
        editorProps: {
            attributes: {
                class: 'w-[400px] font-semibold text-3xl focus:outline-none'
            }
        },
        onUpdate: ({ editor }) => {
            onUpdate(editor);
        }
    });
    const handleUpdateFontSize = (value = 0) => {
        setSize((prevSize) => {
            const newSize = prevSize + value;
            editor?.chain().focus().setFontSize(`${FontSizes[newSize]}`).run();
            return newSize;
        });
    };

    return (
        <div className="tiptap">
            <EditorContent editor={editor} />
            {editor && (
                <BubbleMenu
                    className={`relative flex flex-row gap-4 rounded-lg bg-white px-4 py-2 shadow-tooltip`}
                    editor={editor}
                >
                    <button onClick={() => editor?.chain().focus().toggleBold().run()}>
                        <strong className="text-2xl">B</strong>
                    </button>
                    <button
                        onClick={() => editor?.chain().focus().toggleItalic().run()}
                    >
                        <em className="text-2xl">I</em>
                    </button>
                    <button
                        onClick={() => editor?.chain().focus().toggleUnderline().run()}
                    >
                        <u className="text-2xl">U</u>
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
                        className="disabled:cursor-not-allowed disabled:text-black-900/60"
                    >
                        Undo
                    </button>
                    <button
                        onClick={() => editor?.chain().focus().redo().run()}
                        disabled={!editor.can().redo()}
                        className="disabled:cursor-not-allowed disabled:text-black-900/60"
                    >
                        Redo
                    </button>
                    <div className="flex flex-row items-center justify-center gap-2">
                        <span>{FontSizes[size]}</span>
                        <div className="flex flex-col">
                            <ArrowDown
                                className="h-4 w-4 rotate-180"
                                onClick={() => handleUpdateFontSize(+1)}
                            />
                            <ArrowDown
                                className="h-4 w-4"
                                onClick={() => handleUpdateFontSize(-1)}
                            />
                        </div>
                    </div>
                </BubbleMenu>
            )}
        </div>
    );
}
