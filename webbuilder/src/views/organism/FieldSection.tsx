'use client';

import React from 'react';

import { usePathname, useSearchParams } from 'next/navigation';

import { RadioGroup } from '@headlessui/react';
import cn from 'classnames';
import { GripVertical } from 'lucide-react';
import { DragDropContext, Draggable, DroppableProvided } from 'react-beautiful-dnd';

import { FieldTypes, FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { StrictModeDroppable } from '@app/shared/hocs/StrictModeDroppable';
import { useActiveFieldComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import RequiredIcon from '@app/views/atoms/Icons/Required';

import { ArrowDown } from '../atoms/Icons/ArrowDown';
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

const FieldSection = ({
    slide,
    isScaledDown = false,
    disabled = false
}: {
    slide: FormField;
    isScaledDown?: boolean;
    disabled?: boolean;
}) => {
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
            default:
                return null;
        }
    }

    return (
        <div
            style={{
                backgroundColor: slide?.properties?.theme?.accent
            }}
            className={cn(
                'aspect-video h-min w-full overflow-auto bg-white',
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
                                'flex h-full flex-col justify-center gap-20 px-20 py-10'
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
                                                                    'absolute -left-8 top-1/2 cursor-grab text-black-500',
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
                                                                <input
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
                                                                            'after:content-[*]'
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
    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert('Size greater than 25MB.');
    };
    return (
        <>
            <label
                htmlFor="form-builder-file-upload"
                style={{ borderColor: slide.properties?.theme?.tertiary }}
                className={
                    'flex h-[200px] w-[500px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dotted'
                }
            >
                <FolderUploadIcon
                    style={{ color: slide.properties?.theme?.secondary }}
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

    return (
        <>
            <Input
                slide={slide}
                type="text"
                textColor={slide.properties?.theme?.secondary || 'text-black-500'}
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
                                    className={`flex justify-between rounded-xl border border-cyan-500 p-2 px-4`}
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
    return (
        <>
            {field.type === FieldTypes.DROP_DOWN ? (
                <div
                    style={{
                        borderColor: slide.properties?.theme?.tertiary,
                        color: slide.properties?.theme?.tertiary
                    }}
                    className="mb-2 flex w-full items-center justify-between border-0 border-b-[1px] py-2 text-3xl "
                >
                    <h1>Select an option</h1>
                    <ArrowDown style={{ color: slide.properties?.theme?.secondary }} />
                </div>
            ) : (
                field.properties &&
                field.properties.allowMultipleSelection && (
                    <h1
                        style={{ color: slide.properties?.theme?.secondary }}
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
                            <Input
                                slide={slide}
                                type="text"
                                textColor={
                                    slide.properties?.theme?.secondary ||
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
                        color: slide.properties?.theme?.tertiary,
                        borderColor: slide.properties?.theme?.tertiary
                    }}
                    className={`mt-2 flex w-full justify-between rounded-xl border p-2 py-1 text-[32px]`}
                >
                    Other
                </div>
            )}
            <Button
                style={{
                    color: 'white',
                    background: slide.properties?.theme?.tertiary
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
