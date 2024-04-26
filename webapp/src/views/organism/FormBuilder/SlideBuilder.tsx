'use client';

import { Editor } from '@tiptap/react';
import cn from 'classnames';
import { GripVertical } from 'lucide-react';
import { DragDropContext, Draggable, DroppableProvided } from 'react-beautiful-dnd';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { StrictModeDroppable } from '@app/shared/hocs/StrictModeDroppable';
import { useActiveFieldComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

import DeleteIcon from '../../atoms/Icons/Delete';
import { RichTextEditor } from '../../molecules/RichTextEditor';
import SlideLayoutWrapper from '../Layout/SlideLayoutWrapper';
import FieldDescription from './Fields/FieldDescrption';
import renderFieldWrapper from './Fields/renderField';
import { FieldType } from '@app/store/form-builder/types';

const SlideBuilder = ({ slide, isScaledDown = false, disabled = false }: { slide: StandardFormFieldDto; isScaledDown?: boolean; disabled?: boolean }) => {
    const slideFields = slide?.properties?.fields;
    const { updateTitle, moveFieldInASlide, deleteField } = useFormFieldsAtom();
    const { setActiveFieldComponent, activeFieldComponent } = useActiveFieldComponent();
    const { theme } = useFormState();

    return (
        <SlideLayoutWrapper slide={slide} disabled={disabled} theme={theme} scrollDivId={!disabled ? 'scroll-div' : undefined}>
            <DragDropContext
                onDragEnd={(result, provided) => {
                    if (!result.destination) return;
                    moveFieldInASlide(slide.index, result.source.index, result.destination.index);
                }}
            >
                <StrictModeDroppable droppableId={'fields-droppable-section '}>
                    {(provided: DroppableProvided) => (
                        <div {...provided.droppableProps} ref={provided.innerRef} className={cn('relative w-full flex-1 ')}>
                            <div className="absolute top-[40%] flex w-full flex-col gap-20 px-6 pb-20">
                                {Array.isArray(slideFields) && slideFields.length ? (
                                    slideFields.map((field, index) => {
                                        return (
                                            <Draggable key={field.id} draggableId={`${field.id}`} index={index} disableInteractiveElementBlocking={disabled} isDragDisabled={disabled}>
                                                {(provided) => (
                                                    <div
                                                        id={disabled ? field.id : `scroll-field-${field.id}`}
                                                        className={cn(
                                                            'relative flex h-full w-full flex-row  items-center first:!pt-[0%] last:pb-20',
                                                            slide.properties?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'justify-start' : 'justify-center'
                                                        )}
                                                    >
                                                        <div
                                                            key={index}
                                                            tabIndex={0}
                                                            ref={provided.innerRef}
                                                            className={cn(activeFieldComponent?.id === field.id && 'ring-1 ring-blue-500', 'w-full max-w-[800px] cursor-pointer p-1')}
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
                                                            <div className={'relative flex flex-col items-start'}>
                                                                {!isScaledDown && activeFieldComponent && activeFieldComponent?.id === field.id && (
                                                                    <div
                                                                        className="shadow-bubble absolute -top-14 right-0 cursor-pointer rounded-md bg-white p-2"
                                                                        onClick={() => {
                                                                            deleteField(slide.index, index);
                                                                        }}
                                                                    >
                                                                        <DeleteIcon width={24} height={24} />
                                                                    </div>
                                                                )}
                                                                <div className={cn('text-black-600 absolute -left-8 -mt-3 cursor-grab', 'top-4', isScaledDown ? 'hidden' : '')} {...provided.dragHandleProps}>
                                                                    <GripVertical height={24} width={24} />
                                                                </div>
                                                                <div className={cn(field?.type !== FieldTypes.TEXT && 'mb-2 w-full')}>
                                                                    <div className="relative flex w-full items-center gap-2">
                                                                        {slide?.properties?.showQuestionNumbers && <span className="text-2xl">{index + 1}.</span>}
                                                                        <RichTextEditor
                                                                            field={field}
                                                                            autofocus={field?.type !== FieldType.MATRIX && activeFieldComponent?.id === field.id}
                                                                            onUpdate={(editor: Editor) => updateTitle(field.index, slide.index, editor.getJSON())}
                                                                            isRequired={field?.validations?.required}
                                                                        />
                                                                    </div>
                                                                    <FieldDescription field={field} disabled={disabled} />
                                                                </div>
                                                                {renderFieldWrapper(field, slide, disabled)}
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
                        </div>
                    )}
                </StrictModeDroppable>
            </DragDropContext>
        </SlideLayoutWrapper>
    );
};
export default SlideBuilder;
