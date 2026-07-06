'use client';

import cn from 'classnames';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import MoveUpDown from '@app/views/molecules/form-builder/move-up-down';
import { fieldHasLogic } from '@app/utils/conditional-logic';
import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';
import { AnimatePresence, motion } from 'framer-motion';
import { Trash } from 'lucide-react';
import { RichTextEditor } from '../../molecules/rich-text-editor';
import SlideLayoutWrapper from '../layout/slide-layout-wrapper';
import FieldDescription from './fields/field-description';
import renderFieldWrapper from './fields/render-field';

const SlideBuilder = ({ slide, isScaledDown = false, disabled = false }: { slide: StandardFormFieldDto; isScaledDown?: boolean; disabled?: boolean }) => {
    const slideFields = slide?.properties?.fields;
    const { deleteField } = useFormFieldsAtom();
    const { setActiveFieldComponent, activeFieldComponent } = useActiveFieldComponent();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { theme } = useFormState();
    const { navbarState, setNavbarState } = useNavbarState();

    return (
        <SlideLayoutWrapper showDesktopLayout slide={slide} disabled={disabled} theme={theme} scrollDivId={!disabled ? 'scroll-div' : undefined}>
            <div className="flex h-full w-full flex-col justify-center gap-20 px-6 py-[10vh] ">
                <div className="flex h-full w-full flex-col gap-20 px-6">
                    <AnimatePresence>
                        {Array.isArray(slideFields) && slideFields.length ? (
                            slideFields.map((field, index) => {
                                return (
                                    <motion.div
                                        key={field.id}
                                        {
                                        ...({
                                            initial: { x: navbarState.insertClicked && activeSlideComponent?.id === slide.id ? '-10%' : 0 },
                                            animate: { x: 0 },
                                            transition: { duration: 0.5 },
                                            id: disabled ? field.id : `scroll-field-${field.id}`,
                                            className: cn('relative flex h-full w-full flex-row  items-center first:!pt-[0%]', slide.properties?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'justify-start' : 'justify-center')
                                        } as any)
                                        }
                                    >
                                        <div
                                            key={index}
                                            tabIndex={0}
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
                                        >
                                            <div className={'relative flex flex-col items-start'}>
                                                {!isScaledDown && fieldHasLogic(field) && (
                                                    <div className="text-brand-500 bg-brand-100 absolute -top-6 left-0 z-10 inline-flex items-center gap-1 rounded px-1.5 py-[2px] text-[10px] font-semibold" title="This field is shown/hidden by a logic rule">
                                                        <LogicOutlinedIcon className="h-3 w-3" />
                                                        Logic
                                                    </div>
                                                )}
                                                {!isScaledDown && activeFieldComponent && activeFieldComponent?.id === field.id && (
                                                    <div
                                                        className="shadow-bubble absolute -top-14 right-0 cursor-pointer rounded-md bg-white p-2"
                                                        onClick={() => {
                                                            deleteField(slide.index, index);
                                                        }}
                                                    >
                                                        <Trash width={24} height={24} />
                                                    </div>
                                                )}
                                                {activeFieldComponent?.id === field.id && (
                                                    <div className={cn('text-black-600 absolute -left-10 -mt-1', '', isScaledDown ? 'hidden' : '')}>
                                                        <MoveUpDown slideIndex={slide.index} field={field} />
                                                    </div>
                                                )}
                                                <div className={cn('mb-2 w-full')}>
                                                    <div className="relative flex w-full items-center gap-2">
                                                        {slide?.properties?.showQuestionNumbers && <span className="text-2xl">{index + 1}.</span>}
                                                        <RichTextEditor
                                                            field={field}
                                                            slide={slide}
                                                            // autofocus={field?.type !== FieldType.MATRIX && activeFieldComponent?.id === field.id}
                                                            isRequired={field?.validations?.required}
                                                        />
                                                    </div>
                                                    <FieldDescription field={field} disabled={disabled} />
                                                </div>
                                                {renderFieldWrapper(field, slide, disabled)}
                                            </div>
                                        </div>
                                    </motion.div>
                                );
                            })
                        ) : !disabled && !isScaledDown ? (
                            // An empty page shouldn't be a dead rectangle — give
                            // first-run creators a direct way in (audit B4).
                            <div className="flex h-full w-full items-center justify-center">
                                <button
                                    type="button"
                                    className="border-black-400 text-black-700 hover:border-black-600 hover:text-black-900 flex flex-col items-center gap-2 rounded-xl border border-dashed bg-white/60 px-10 py-8 text-sm font-medium transition-colors"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        setNavbarState({ ...navbarState, insertMenuOpen: true });
                                    }}
                                >
                                    <span className="text-2xl leading-none">＋</span>
                                    Add a question
                                    <span className="text-black-500 text-xs font-normal">Pick a field type from the Insert menu</span>
                                </button>
                            </div>
                        ) : (
                            <></>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </SlideLayoutWrapper >
    );
};
export default SlideBuilder;
