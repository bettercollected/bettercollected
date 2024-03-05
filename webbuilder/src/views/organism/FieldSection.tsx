'use client';

import { useState } from 'react';

import { RadioGroup } from '@headlessui/react';
import { Color } from '@tiptap/extension-color';
import TextStyle from '@tiptap/extension-text-style';
import Underline from '@tiptap/extension-underline';
import { BubbleMenu, Editor, EditorContent, useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import cn from 'classnames';
import { GripVertical } from 'lucide-react';
import { DragDropContext, Draggable, DroppableProvided } from 'react-beautiful-dnd';
import { HexColorPicker } from 'react-colorful';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { StrictModeDroppable } from '@app/shared/hocs/StrictModeDroppable';
import { useActiveFieldComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { FontSize } from '@app/utils/richTextEditorExtenstion/fontSize';
import RequiredIcon from '@app/views/atoms/Icons/Required';

import { ArrowDown } from '../atoms/Icons/ArrowDown';
import { ArrowUp } from '../atoms/Icons/ArrowUp';
import DeleteIcon from '../atoms/Icons/Delete';
import { FolderUploadIcon } from '../atoms/Icons/FolderUploadIcon';
import { PlusIcon } from '../atoms/Icons/Plus';

function getPlaceholderValueForTitle(fieldType: FieldTypes) {
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

function getPlaceholderValueForField(fieldType: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.EMAIL:
            return 'name@gmail.com';
        case FieldTypes.NUMBER:
            return '123';
        case FieldTypes.SHORT_TEXT:
            return 'Answer';
        case FieldTypes.LINK:
            return 'https://';
        case FieldTypes.PHONE_NUMBER:
            return '0123456789';
        default:
            return 'No Field Selected';
    }
}

function getClassName(fieldType: FieldTypes) {
    switch (fieldType) {
        case FieldTypes.TEXT:
            return 'text-[32px] font-bold';
        case FieldTypes.EMAIL:
        case FieldTypes.NUMBER:
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LINK:
        case FieldTypes.PHONE_NUMBER:
        case FieldTypes.FILE_UPLOAD:
        case FieldTypes.YES_NO:
        case FieldTypes.DROP_DOWN:
        case FieldTypes.MULTIPLE_CHOICE:
            return '';
        default:
            return '';
    }
}

const FieldSection = ({
    slide,
    isScaledDown = false,
    disabled = false
}: {
    slide: FormField;
    isScaledDown?: boolean;
    disabled?: boolean;
}) => {
    const { theme } = useFormState();
    const slideFields = slide?.properties?.fields;
    const { updateTitle, updateDescription, moveFieldInASlide, deleteField } =
        useFormFieldsAtom();
    const { setActiveFieldComponent, activeFieldComponent } = useActiveFieldComponent();
    function renderField(field: FormField) {
        switch (field.type) {
            case FieldTypes.EMAIL:
            case FieldTypes.NUMBER:
            case FieldTypes.SHORT_TEXT:
            case FieldTypes.LINK:
            case FieldTypes.PHONE_NUMBER:
                return <InputField field={field} slide={slide} disabled={disabled} />;
            case FieldTypes.FILE_UPLOAD:
                return <FileUpload field={field} slide={slide} disabled={disabled} />;
            case FieldTypes.YES_NO:
                return <YesNoField field={field} slide={slide} disabled={disabled} />;
            case FieldTypes.DROP_DOWN:
            case FieldTypes.MULTIPLE_CHOICE:
                return (
                    <DropDownField field={field} slide={slide} disabled={disabled} />
                );
            case FieldTypes.TEXT:
                return <></>;
            default:
                return null;
        }
    }

    function getEditors(field: FormField) {
        return useEditor({
            extensions: [StarterKit, TextStyle, FontSize, Underline, Color],
            content: getPlaceholderValueForTitle(field.type || FieldTypes.SHORT_TEXT),
            editorProps: {
                attributes: {
                    class: 'w-[400px] font-semibold text-3xl focus:outline-none'
                }
            },
            onUpdate: ({ editor }) => {
                console.log('updated Text : ', editor.getText(), editor.getHTML());
            }
        });
    }

    const TitleEditors = slideFields?.map((field) => getEditors(field)) ?? [
        new Editor({ extensions: [StarterKit, FontSize] })
    ];

    return (
        <div
            style={{
                backgroundColor: slide?.properties?.theme?.accent || theme?.accent
            }}
            className={cn(
                'aspect-video h-min w-full  overflow-auto bg-white',
                disabled ? 'pointer-events-none overflow-hidden' : '',
                isScaledDown ? '!h-full !w-full' : ''
            )}
        >
            <DragDropContext
                onDragEnd={(result, provided) => {
                    if (!result.destination) return;
                    moveFieldInASlide(
                        slide.index,
                        result.source.index,
                        result.destination.index
                    );
                }}
            >
                <StrictModeDroppable droppableId={'fields-droppable-section'}>
                    {(provided: DroppableProvided) => (
                        <div
                            {...provided.droppableProps}
                            ref={provided.innerRef}
                            className={cn(
                                'flex h-min flex-col justify-center gap-20 px-20 py-60'
                            )}
                        >
                            {Array.isArray(slideFields) && slideFields.length ? (
                                slideFields.map((field, index) => {
                                    return (
                                        <Draggable
                                            key={index}
                                            draggableId={`${index}`}
                                            index={index}
                                            disableInteractiveElementBlocking={disabled}
                                            isDragDisabled={disabled}
                                        >
                                            {(provided) => (
                                                <div
                                                    className={cn(
                                                        'flex flex-row gap-1'
                                                    )}
                                                >
                                                    <div
                                                        key={index}
                                                        tabIndex={0}
                                                        ref={provided.innerRef}
                                                        className={cn(
                                                            activeFieldComponent?.id ===
                                                                field.id &&
                                                                'ring-1 ring-blue-500',
                                                            'w-fit cursor-pointer p-1'
                                                        )}
                                                        onFocus={(event) => {
                                                            event.preventDefault();
                                                            event.stopPropagation();
                                                            setActiveFieldComponent({
                                                                id: field.id,
                                                                index: index
                                                            });
                                                        }}
                                                        onClick={(event) => {
                                                            event.preventDefault();
                                                            event.stopPropagation();
                                                            setActiveFieldComponent({
                                                                id: field.id,
                                                                index: index
                                                            });
                                                        }}
                                                        {...provided.draggableProps}
                                                    >
                                                        <div
                                                            className={
                                                                'relative flex flex-col items-start'
                                                            }
                                                        >
                                                            <div
                                                                className={cn(
                                                                    'absolute -left-8 cursor-grab text-black-500',
                                                                    field.type ===
                                                                        FieldTypes.TEXT
                                                                        ? 'top-1/3'
                                                                        : 'top-1/2',
                                                                    isScaledDown
                                                                        ? 'hidden'
                                                                        : ''
                                                                )}
                                                                {...provided.dragHandleProps}
                                                            >
                                                                <GripVertical />
                                                            </div>
                                                            <div className="relative flex items-center gap-2">
                                                                {slide?.properties
                                                                    ?.showQuestionNumbers && (
                                                                    <span className="text-2xl">
                                                                        {index + 1}.
                                                                    </span>
                                                                )}
                                                                {/* <input
                                                                    id={`input-${disabled ? `${slide.id}${field.id}` : field.id}`}
                                                                    placeholder={getPlaceholderValueForTitle(
                                                                        field.type ||
                                                                            FieldTypes.SHORT_TEXT
                                                                    )}
                                                                    type="text"
                                                                    className={cn(
                                                                        '-left-1 border-0 px-0 text-2xl',
                                                                        field
                                                                            ?.validations
                                                                            ?.required &&
                                                                            'after:content-[*]',
                                                                        getClassName(
                                                                            field.type ||
                                                                                FieldTypes.SHORT_TEXT
                                                                        )
                                                                    )}
                                                                    value={field.title}
                                                                    onChange={(
                                                                        e: any
                                                                    ) =>
                                                                        updateTitle(
                                                                            field.index,
                                                                            slide.index,
                                                                            e.target
                                                                                .value
                                                                        )
                                                                    }
                                                                /> */}
                                                                <MenuBar
                                                                    editor={
                                                                        TitleEditors[
                                                                            index
                                                                        ]
                                                                    }
                                                                />
                                                                <EditorContent
                                                                    editor={
                                                                        TitleEditors[
                                                                            index
                                                                        ]
                                                                    }
                                                                />

                                                                {field?.validations
                                                                    ?.required && (
                                                                    <div className="absolute -right-2 top-4 text-red-500">
                                                                        <RequiredIcon />
                                                                    </div>
                                                                )}
                                                            </div>
                                                            {field?.description !==
                                                                undefined && (
                                                                <input
                                                                    id={`input-${disabled ? `${slide.id}${field.id}` : field.id}`}
                                                                    placeholder={getPlaceholderValueForTitle(
                                                                        field.type ||
                                                                            FieldTypes.SHORT_TEXT
                                                                    )}
                                                                    className={
                                                                        'text-md ring-none -left-1 border-0 px-0 py-0 text-black-800 outline-none '
                                                                    }
                                                                    type="text"
                                                                    value={
                                                                        field.description
                                                                    }
                                                                    onChange={(
                                                                        e: any
                                                                    ) =>
                                                                        updateDescription(
                                                                            field.index,
                                                                            slide.index,
                                                                            e.target
                                                                                .value
                                                                        )
                                                                    }
                                                                />
                                                            )}
                                                            {renderField(field)}
                                                        </div>
                                                    </div>
                                                    {!isScaledDown &&
                                                        activeFieldComponent &&
                                                        activeFieldComponent?.id ===
                                                            field.id && (
                                                            <Button
                                                                icon={<DeleteIcon />}
                                                                variant={'danger'}
                                                                onClick={() =>
                                                                    deleteField(
                                                                        slide.index,
                                                                        index
                                                                    )
                                                                }
                                                            />
                                                        )}
                                                </div>
                                            )}
                                        </Draggable>
                                    );
                                })
                            ) : (
                                <></>
                            )}
                            {provided.placeholder}
                        </div>
                    )}
                </StrictModeDroppable>
            </DragDropContext>
        </div>
    );
};
export default FieldSection;

const FileUpload = ({
    field,
    slide,
    disabled
}: {
    field: FormField;
    slide: FormField;
    disabled: boolean;
}) => {
    const { theme } = useFormState();

    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert('Size greater than 25MB.');
    };
    return (
        <>
            <label
                htmlFor="form-builder-file-upload"
                style={{
                    borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                }}
                className={
                    'flex h-[200px] w-[500px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dotted'
                }
            >
                <FolderUploadIcon
                    style={{
                        color: slide.properties?.theme?.secondary || theme?.secondary
                    }}
                />
                <div className={'flex flex-col items-center gap-1'}>
                    <span className={'text-base font-semibold'}>
                        Choose your file or drag file
                    </span>
                    <span className={'text-[12px]'}>Max size limit: 25 MB</span>
                </div>
            </label>
            <input
                type="file"
                id="form-builder-file-upload"
                className={'invisible'}
                onChange={handleFileInputChange}
            />
        </>
    );
};

const InputField = ({
    field,
    slide,
    disabled
}: {
    field: FormField;
    slide: FormField;
    disabled: boolean;
}) => {
    const { updateFieldPlaceholder } = useFormFieldsAtom();
    const { theme } = useFormState();

    return (
        <>
            <FieldInput
                $slide={slide}
                type="text"
                $formTheme={theme}
                textColor={
                    slide.properties?.theme?.secondary ||
                    theme?.secondary ||
                    'text-black-500'
                }
                value={field.properties?.placeholder}
                placeholder={getPlaceholderValueForField(
                    field.type || FieldTypes.SHORT_TEXT
                )}
                onChange={(e: any) =>
                    updateFieldPlaceholder(field.index, slide.index, e.target.value)
                }
            />
        </>
    );
};

const YesNoField = ({
    field,
    slide,
    disabled
}: {
    field: FormField;
    slide: FormField;
    disabled: boolean;
}) => {
    const { theme } = useFormState();

    return (
        <>
            <RadioGroup
                className={'flex w-full flex-col gap-2'}
                value={field.value}
                onChange={() => {}}
            >
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <RadioGroup.Option value={choice.value} key={index}>
                                <div
                                    style={{
                                        borderColor:
                                            slide.properties?.theme?.tertiary ||
                                            theme?.tertiary
                                    }}
                                    className={`flex justify-between rounded-xl border p-2 px-4`}
                                >
                                    {choice.value}
                                </div>
                            </RadioGroup.Option>
                        );
                    })}
            </RadioGroup>
        </>
    );
};

const DropDownField = ({
    field,
    slide,
    disabled
}: {
    field: FormField;
    slide: FormField;
    disabled: boolean;
}) => {
    const { updateChoiceFieldValue, addChoiceField } = useFormFieldsAtom();
    const { theme } = useFormState();
    return (
        <>
            {field.type === FieldTypes.DROP_DOWN ? (
                <div
                    style={{
                        borderColor:
                            slide.properties?.theme?.tertiary || theme?.tertiary,
                        color: slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className="mb-2 flex w-full items-center justify-between border-0 border-b-[1px] py-2 text-3xl "
                >
                    <h1>Select an option</h1>
                    <ArrowDown
                        style={{
                            color:
                                slide.properties?.theme?.secondary || theme?.secondary
                        }}
                    />
                </div>
            ) : (
                field.properties &&
                field.properties.allowMultipleSelection && (
                    <h1
                        style={{
                            color:
                                slide.properties?.theme?.secondary || theme?.secondary
                        }}
                        className="-mt-1 mb-1 font-medium"
                    >
                        Choose as many as you like
                    </h1>
                )
            )}
            <div className={'flex w-full flex-col gap-2'}>
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <FieldInput
                                $slide={slide}
                                type="text"
                                $formTheme={theme}
                                textColor={
                                    slide.properties?.theme?.secondary ||
                                    theme?.secondary ||
                                    'text-black-500'
                                }
                                value={choice.value}
                                key={index}
                                placeholder={`Item ${index + 1}`}
                                onChange={(e: any) =>
                                    updateChoiceFieldValue(
                                        field.index,
                                        slide.index,
                                        choice.id,
                                        e.target.value
                                    )
                                }
                                className={`flex justify-between rounded-xl border p-2 px-4`}
                            />
                        );
                    })}
            </div>
            {field?.properties?.allowOtherOption && (
                <div
                    style={{
                        color: slide.properties?.theme?.tertiary || theme?.tertiary,
                        borderColor:
                            slide.properties?.theme?.tertiary || theme?.tertiary
                    }}
                    className={`mt-2 flex w-full justify-between rounded-xl border p-2 py-1 text-[32px]`}
                >
                    Other
                </div>
            )}
            <Button
                style={{
                    color: 'white',
                    background: slide.properties?.theme?.tertiary || theme?.tertiary
                }}
                onClick={() => addChoiceField(field.index, slide.index)}
                variant={'ghost'}
                className="mt-2 text-lg font-semibold"
                icon={<PlusIcon className="h-4 w-4" />}
            >
                Add Option
            </Button>
        </>
    );
};

const MenuBar = ({ editor }: { editor: Editor | null }) => {
    const FontSizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 64];
    const [size, setSize] = useState(5);
    const [showColorPicker, setShowColorPicker] = useState(false);
    const [color, setColor] = useState('#aabbcc');
    return (
        <>
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
                                onClick={() => {
                                    setSize(size + 1);
                                    editor
                                        ?.chain()
                                        .focus()
                                        .setFontSize(`${FontSizes[size]}`)
                                        .run();
                                }}
                            />
                            <ArrowDown
                                className="h-4 w-4"
                                onClick={() => {
                                    setSize(size - 1);
                                    editor
                                        ?.chain()
                                        .focus()
                                        .setFontSize(`${FontSizes[size]}`)
                                        .run();
                                }}
                            />
                        </div>
                    </div>
                </BubbleMenu>
            )}
        </>
    );
};
