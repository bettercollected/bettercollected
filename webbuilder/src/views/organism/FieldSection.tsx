'use client';

import { useState } from 'react';

import Image from 'next/image';

import { RadioGroup } from '@headlessui/react';
import { Editor } from '@tiptap/react';
import cn from 'classnames';
import { GripVertical } from 'lucide-react';
import { DragDropContext, Draggable, DroppableProvided } from 'react-beautiful-dnd';

import RectangleImage from '@app/assets/image/rectangle.png';
import { FieldTypes, FormField } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { StrictModeDroppable } from '@app/shared/hocs/StrictModeDroppable';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { getPlaceholderValueForField } from '@app/utils/formUtils';
import RequiredIcon from '@app/views/atoms/Icons/Required';

import { ArrowDown } from '../atoms/Icons/ArrowDown';
import DeleteIcon from '../atoms/Icons/Delete';
import { FolderUploadIcon } from '../atoms/Icons/FolderUploadIcon';
import { PlusIcon } from '../atoms/Icons/Plus';
import {
    RichTextEditor,
    getPlaceholderValueForTitle
} from '../molecules/RichTextEditor';

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
    // layout = FormSlideLayout.TWO_COLUMN_LEFT,
    isScaledDown = false,
    disabled = false
}: {
    slide: FormField;
    // layout: FormSlideLayout,
    isScaledDown?: boolean;
    disabled?: boolean;
}) => {
    const { theme } = useFormState();
    const slideFields = slide?.properties?.fields;
    const {
        activeSlide,
        updateTitle,
        updateDescription,
        moveFieldInASlide,
        deleteField
    } = useFormFieldsAtom();
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

    return (
        <div
            style={{
                backgroundColor: slide?.properties?.theme?.accent || theme?.accent
            }}
            className={cn(
                'grid aspect-video h-min w-full grid-cols-2 overflow-hidden rounded-lg bg-white',
                disabled ? 'pointer-events-none overflow-hidden' : '',
                isScaledDown ? '!h-full !w-full' : ''
                // slide.imageUrl ? 'grid-cols-2' : 'grid-cols-1'
            )}
        >
            <div
                className={cn(
                    'grid-cols-1 overflow-x-hidden',
                    slide &&
                        slide?.properties?.layout ===
                            FormSlideLayout.TWO_COLUMN_RIGHT
                        ? 'order-1'
                        : slide &&
                            slide?.properties?.layout ===
                                FormSlideLayout.TWO_COLUMN_LEFT
                          ? 'order-0'
                          : '' // Add a default case or handle the case when layout is neither 'two-column-right' nor 'two-column-left'
                )}
            >
                <ScrollArea className="h-full flex-1 overflow-y-auto">
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
                                        'grid h-full grid-cols-1 justify-center gap-5 px-20 py-60'
                                    )}
                                >
                                    {Array.isArray(slideFields) &&
                                    slideFields.length ? (
                                        slideFields.map((field, index) => {
                                            return (
                                                <Draggable
                                                    key={field.id}
                                                    draggableId={`${field.id}`}
                                                    index={index}
                                                    disableInteractiveElementBlocking={
                                                        disabled
                                                    }
                                                    isDragDisabled={disabled}
                                                >
                                                    {(provided) => (
                                                        <div
                                                            className={cn(
                                                                'relative flex flex-row pb-20'
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
                                                                    'w-full max-w-[600px] cursor-pointer p-1'
                                                                )}
                                                                onFocus={(event) => {
                                                                    event.preventDefault();
                                                                    event.stopPropagation();
                                                                    setActiveFieldComponent(
                                                                        {
                                                                            id: field.id,
                                                                            index: index
                                                                        }
                                                                    );
                                                                }}
                                                                onClick={(event) => {
                                                                    event.preventDefault();
                                                                    event.stopPropagation();
                                                                    setActiveFieldComponent(
                                                                        {
                                                                            id: field.id,
                                                                            index: index
                                                                        }
                                                                    );
                                                                }}
                                                                {...provided.draggableProps}
                                                            >
                                                                <div
                                                                    className={
                                                                        'relative flex flex-col items-start'
                                                                    }
                                                                >
                                                                    {!isScaledDown &&
                                                                        activeFieldComponent &&
                                                                        activeFieldComponent?.id ===
                                                                            field.id && (
                                                                            <div
                                                                                className="absolute -top-14 right-0 cursor-pointer rounded-md bg-white p-2 shadow-bubble"
                                                                                onClick={() => {
                                                                                    deleteField(
                                                                                        slide.index,
                                                                                        index
                                                                                    );
                                                                                }}
                                                                            >
                                                                                <DeleteIcon
                                                                                    width={
                                                                                        24
                                                                                    }
                                                                                    height={
                                                                                        24
                                                                                    }
                                                                                />
                                                                            </div>
                                                                        )}
                                                                    <div
                                                                        className={cn(
                                                                            'absolute -left-8 -mt-3 cursor-grab text-black-500',
                                                                            'top-1/2',
                                                                            isScaledDown
                                                                                ? 'hidden'
                                                                                : ''
                                                                        )}
                                                                        {...provided.dragHandleProps}
                                                                    >
                                                                        <GripVertical
                                                                            height={24}
                                                                            width={24}
                                                                        />
                                                                    </div>
                                                                    <div className="relative w-full items-center gap-2">
                                                                        {slide
                                                                            ?.properties
                                                                            ?.showQuestionNumbers && (
                                                                            <span className="text-2xl">
                                                                                {index +
                                                                                    1}
                                                                                .
                                                                            </span>
                                                                        )}
                                                                        <RichTextEditor
                                                                            field={
                                                                                field
                                                                            }
                                                                            onUpdate={(
                                                                                editor: Editor
                                                                            ) =>
                                                                                updateTitle(
                                                                                    field.index,
                                                                                    slide.index,
                                                                                    editor.getJSON()
                                                                                )
                                                                            }
                                                                        />
                                                                        {field
                                                                            ?.validations
                                                                            ?.required && (
                                                                            <div className="absolute -right-6 top-0 text-red-500">
                                                                                <RequiredIcon />
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                    {field?.description !==
                                                                        undefined &&
                                                                        field?.description !==
                                                                            null && (
                                                                            <input
                                                                                id={`input-${disabled ? `${slide.id}${field.id}` : field.id}`}
                                                                                placeholder={getPlaceholderValueForTitle(
                                                                                    field.type ||
                                                                                        FieldTypes.SHORT_TEXT
                                                                                )}
                                                                                className={
                                                                                    'text-md ring-none -left-1 w-full border-0 px-0 py-0 text-black-800 outline-none '
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
                                                                                        e
                                                                                            .target
                                                                                            .value
                                                                                    )
                                                                                }
                                                                            />
                                                                        )}
                                                                    {renderField(field)}
                                                                </div>
                                                            </div>
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
                </ScrollArea>
            </div>
            <div className="grid-cols-1 ">
                <Image
                    objectFit="cover"
                    className={cn(
                        'h-full w-full',
                        slide && slide?.properties?.layout ===
                                FormSlideLayout.TWO_COLUMN_RIGHT
                            ? 'order-0'
                            : slide && slide?.properties?.layout ===
                                    FormSlideLayout.TWO_COLUMN_LEFT
                              ? 'order-1'
                              : ''
                    )}
                    src={RectangleImage}
                    alt="LayoutImage"
                />
            </div>
            {/* <div className="basis-1/2">
                {slide.imageUrl && (
                    <Image
                        className="h-full w-full"
                        objectFit="cover"
                        src={slide.imageUrl}
                        width={2000}
                        height={2000}
                        alt="LayoutImage"
                    />
                )}
            </div> */}
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
