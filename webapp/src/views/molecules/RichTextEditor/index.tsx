import Color from '@tiptap/extension-color';
import TextStyle from '@tiptap/extension-text-style';
import Underline from '@tiptap/extension-underline';
import { Editor, EditorProvider, useCurrentEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { FontSize } from '@app/utils/richTextEditorExtenstion/fontSize';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { ArrowDown } from '@app/views/atoms/Icons/ArrowDown';
import RequiredIcon from '@app/views/atoms/Icons/Required';
import { useEffect, useState } from 'react';

export function getPlaceholderValueForTitle(fieldType: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.EMAIL:
            return 'Enter Your Email Address';
        case FieldTypes.NUMBER:
            return 'Enter Number';
        case FieldTypes.SHORT_TEXT:
            return 'Enter Question';
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
        case FieldTypes.RATING:
            return 'Rate from 1 to 5';
        case FieldTypes.DATE:
            return 'Select a date';
        case FieldTypes.LINEAR_RATING:
            return 'Rate from 1 to 10';
        case FieldTypes.MATRIX:
            return 'Matrix Field';
        default:
            return 'No Field Selected';
    }
}

export const Extenstions = [StarterKit, TextStyle, FontSize, Underline, Color];

export function RichTextEditor({ field, onUpdate, autofocus = false, isRequired = false }: { field: StandardFormFieldDto; onUpdate: (editor: any) => void; autofocus?: boolean; isRequired?: boolean }) {
    const getContentForEditor = () => {
        return field.title
            ? getHtmlFromJson(field.title ?? '')
            : `
        <p><strong>${getPlaceholderValueForTitle(field.type || FieldTypes.SHORT_TEXT)}</strong></p>
      `;
    };

    return (
        <div className="tiptap group relative flex w-full justify-between">
            <EditorProvider
                content={getContentForEditor()}
                extensions={Extenstions}
                slotBefore={<TiptapMenuBar />}
                autofocus={autofocus}
                editorProps={{
                    attributes: {
                        class: 'outline-none font-medium w-full max-w-full min-w-[300px]',
                        style: 'word-break: break-word'
                    }
                }}
                onFocus={({ editor }) => {
                    // if (
                    //     editor.getHTML() ===
                    //     `<p><strong>${getPlaceholderValueForTitle(field.type || FieldTypes.SHORT_TEXT)}</strong></p>`
                    // )
                    editor.commands.focus('all');
                }}
                onUpdate={({ editor }) => {
                    onUpdate(editor);
                    console.log(editor.getHTML(), editor?.isActive('bold'));
                    // editor?.isActive('bold') && editor?.chain().focus().setBold().run();
                    if (editor.getText() === '') {
                        editor?.chain().focus().setBold().run();
                    }
                }}
            >
                {''}
            </EditorProvider>
            {isRequired && (
                <div className="h-5 w-5">
                    <RequiredIcon />
                </div>
            )}
        </div>
    );
}

const getActiveFontSize = (editor?: Editor) => {
    if (!editor) return null;
    const fontSize = editor.getAttributes('textStyle')?.fontSize || '';
    const fontSizeInNum = Number((fontSize.match(/\d+/g) || []).join(''));
    return fontSizeInNum;
};

const TiptapMenuBar = () => {
    const editorRef = useCurrentEditor();
    const FontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64];
    const editor = editorRef.editor;
    if (!editor) {
        return null;
    }

    const handleUpdateFontSize = (value = 0) => {
        const activeFontSize = (getActiveFontSize(editor) as number) || 18;
        const currentActiveIndex = FontSizes.findIndex((num) => num == activeFontSize);
        const newSize = currentActiveIndex + value;
        editor?.chain().focus().setFontSize(`${FontSizes[newSize]}`).run();
    };

    return (
        <button
            className={cn(`shadow-tooltip absolute -top-14 mb-2 hidden items-center rounded-lg bg-white px-4 py-1`, 'group-focus-within:flex')}
            tabIndex={0}
            onClick={() => {
                return true;
            }}
        >
            <div className="flex flex-row items-center justify-center gap-4">
                <span className="p3-new font-medium">Text</span>
                <div className="flex items-center gap-1">
                    <span className="p3-new text-black-700 w-[21px]">{getActiveFontSize(editor) || 18}</span>
                    <div className="flex flex-col">
                        <div
                            className="cursor-pointer"
                            onClick={() => {
                                handleUpdateFontSize(+1);
                            }}
                        >
                            <ArrowDown className="h-4 w-4 rotate-180" />
                        </div>
                        <div
                            className="cursor-pointer"
                            onClick={() => {
                                handleUpdateFontSize(-1);
                            }}
                        >
                            <ArrowDown className="h-4 w-4" />
                        </div>
                    </div>
                </div>
                <div
                    onClick={() => {
                        editor?.chain().focus().toggleBold().run();
                    }}
                    className={cn('cursor-pointer rounded', editor?.isActive('bold') && 'bg-gray-200')}
                >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path
                            d="M6.51811 19V5.18182H11.5785C12.5591 5.18182 13.371 5.34375 14.0142 5.66761C14.6574 5.98698 15.1387 6.42105 15.4581 6.96982C15.7775 7.51409 15.9371 8.12808 15.9371 8.81179C15.9371 9.38755 15.8314 9.87334 15.62 10.2692C15.4086 10.6605 15.1252 10.9754 14.7699 11.2138C14.419 11.4477 14.0322 11.6186 13.6094 11.7266V11.8615C14.0682 11.884 14.5157 12.0324 14.9521 12.3068C15.3929 12.5767 15.7572 12.9613 16.0451 13.4606C16.333 13.9599 16.4769 14.5671 16.4769 15.2823C16.4769 15.9885 16.3105 16.6228 15.9776 17.185C15.6493 17.7428 15.141 18.1858 14.4528 18.5142C13.7646 18.8381 12.8852 19 11.8146 19H6.51811ZM8.60298 17.212H11.6122C12.6108 17.212 13.326 17.0186 13.7578 16.6317C14.1896 16.2449 14.4055 15.7614 14.4055 15.1811C14.4055 14.7448 14.2953 14.3445 14.0749 13.9801C13.8545 13.6158 13.5397 13.3256 13.1303 13.1097C12.7255 12.8938 12.2442 12.7859 11.6864 12.7859H8.60298V17.212ZM8.60298 11.1598H11.3963C11.8641 11.1598 12.2847 11.0698 12.658 10.8899C13.0359 10.71 13.335 10.4581 13.5554 10.1342C13.7803 9.80587 13.8928 9.41903 13.8928 8.97372C13.8928 8.40246 13.6926 7.92341 13.2923 7.53658C12.8919 7.14974 12.2779 6.95632 11.4503 6.95632H8.60298V11.1598Z"
                            fill="#4D4D4D"
                        />
                    </svg>
                </div>
                <div onClick={() => editor?.chain().focus().toggleItalic().run()} className={cn('cursor-pointer rounded', editor?.isActive('italic') && 'bg-gray-200')}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path
                            d="M11.3 5.36C11.3267 5.34667 11.44 5.34 11.64 5.34C13.1733 5.40667 14.8 5.41333 16.52 5.36C16.9333 5.34667 17.1667 5.38 17.22 5.46C17.2467 5.5 17.2333 5.65333 17.18 5.92C17.1133 6.22667 17.0467 6.39333 16.98 6.42C16.9133 6.44667 16.68 6.46 16.28 6.46C15.6533 6.47333 15.2867 6.50667 15.18 6.56C15.1133 6.58667 15.0667 6.63333 15.04 6.7C14.9733 6.88667 14.5 8.72667 13.62 12.22C12.7 15.9133 12.2467 17.7667 12.26 17.78C12.2867 17.8467 12.7133 17.88 13.54 17.88H13.98L14.06 17.94C14.1 17.9933 14.12 18.04 14.12 18.08L13.94 18.88C13.9 18.96 13.76 18.9933 13.52 18.98C13.4533 18.98 13.3267 18.98 13.14 18.98C11.06 18.9267 9.43333 18.9333 8.26 19H8.02L7.96 18.94C7.90667 18.8867 7.88 18.84 7.88 18.8L8.06 18C8.1 17.92 8.28667 17.88 8.62 17.88C8.68667 17.88 8.76667 17.88 8.86 17.88C9.56667 17.8667 9.97333 17.8133 10.08 17.72C10.0933 17.7067 10.5667 15.8533 11.5 12.16C12.42 8.48 12.88 6.62667 12.88 6.6C12.88 6.58667 12.8667 6.56667 12.84 6.54C12.7733 6.5 12.4267 6.47333 11.8 6.46H11.16L11.08 6.38C11.0133 6.31333 11.02 6.13333 11.1 5.84C11.18 5.56 11.2467 5.4 11.3 5.36Z"
                            fill="#4D4D4D"
                        />
                    </svg>
                </div>
                <div onClick={() => editor?.chain().focus().toggleUnderline().run()} className={cn('cursor-pointer rounded', editor?.isActive('underline') && 'bg-gray-200')}>
                    <u className="px-1 text-xl">U</u>
                </div>
            </div>
        </button>
    );
};
