import { ReactNode } from 'react';

import { AnimatePresence, motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes } from '@app/models/dtos/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useNavbarState } from '@app/store/jotai/navbar';
import DeleteIcon from '@app/views/atoms/Icons/Delete';

import AddSlidePopover from './AddSlide/AddSlidePopover';
import SlideBuilder from './SlideBuilder';
import SlideOptions from './SlideOptions';
import ThankYouSlide from './ThankYouPage';
import WelcomeSlide from './WelcomePage';

export default function LeftDrawer({}: {}) {
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { formFields, addField, deleteActiveSlide } = useFormFieldsAtom();
    const Slides = formFields;
    const { navbarState, setNavbarState } = useNavbarState();

    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add questions');
            return;
        }

        if (activeSlideComponent?.index < 0) {
            toast('Select a slide to add questions');
            return;
        }

        const fieldId = v4();
        if (
            field.type === FieldTypes.YES_NO ||
            field.type === FieldTypes.DROP_DOWN ||
            field.type === FieldTypes.MULTIPLE_CHOICE
        ) {
            const firstChoiceId = v4();
            const secondChoiceId = v4();
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type,
                    properties: {
                        fields: [],
                        choices: [
                            {
                                id: firstChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'Yes' : ''
                            },
                            {
                                id: secondChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'No' : ''
                            }
                        ]
                    }
                },
                activeSlideComponent?.index || 0
            );
        } else if (
            field.type === FieldTypes.RATING ||
            field.type === FieldTypes.LINEAR_RATING
        ) {
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent!.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent!.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type,
                    properties: {
                        fields: [],
                        steps: field.type === FieldTypes.RATING ? 5 : 10
                    }
                },
                activeSlideComponent?.index || 0
            );
        } else {
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent!.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent!.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type
                },
                activeSlideComponent?.index || 0
            );
        }
        setNavbarState({ insertClicked: false });
        window.setTimeout(function () {
            document.getElementById(`input-${fieldId}`)?.focus();
        }, 0);
    };

    return (
        <>
            <div
                id="slides-preview"
                className="flex h-body-content w-[200px] flex-col gap-5 overflow-y-auto overflow-x-hidden border-r border-r-black-300 bg-white"
            >
                <div className="flex w-full items-center justify-between border-b border-b-black-400 p-5">
                    <span className="h4-new font-medium text-black-700">Pages</span>
                    <AddSlidePopover />
                </div>
                <div className=" flex flex-1 flex-col justify-between overflow-auto">
                    <div className="border-b border-b-black-400 !px-2">
                        <div
                            className={cn(
                                'mb-6 rounded-lg border border-transparent px-2 pb-2 pt-1',
                                activeSlideComponent?.id === 'welcome-page' &&
                                    'border-pink-500'
                            )}
                        >
                            <div className="p2-new mb-1 font-medium text-black-700">
                                Welcome
                            </div>
                            <div
                                className={cn(
                                    ' relative flex !aspect-video cursor-pointer items-center justify-center overflow-auto rounded-lg bg-white'
                                )}
                                onClick={() => {
                                    setActiveSlideComponent({
                                        id: 'welcome-page',
                                        index: -10
                                    });
                                }}
                            >
                                <WelcomeSlide disabled />
                            </div>
                        </div>
                    </div>
                    <ScrollArea className="max-h-pages-container flex-1  overflow-y-auto">
                        <div className="flex  w-[200px]  flex-col gap-2  px-2 py-6">
                            {Array.isArray(Slides) && Slides.length ? (
                                Slides.map((slide, index) => {
                                    return (
                                        <div
                                            key={slide.id}
                                            className={cn(
                                                'rounded-lg border border-transparent px-2 pb-2 pt-1',
                                                activeSlideComponent?.id === slide.id &&
                                                    '!border-pink-500'
                                            )}
                                        >
                                            <div className="flex w-full justify-between">
                                                <div className="p2-new mb-1 font-medium text-black-700">
                                                    Page {index + 1}
                                                </div>
                                                <SlideOptions
                                                    slideIndex={slide.index}
                                                />
                                            </div>
                                            <div
                                                key={slide.id}
                                                className={cn(
                                                    'relative flex items-center gap-2' //h-[93.28px] w-[165.83px]
                                                )}
                                            >
                                                <div
                                                    role="button"
                                                    className={cn(
                                                        'flex !aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-lg border'
                                                    )}
                                                    onClick={() => {
                                                        setActiveSlideComponent({
                                                            id: slide.id,
                                                            index
                                                        });
                                                    }}
                                                >
                                                    <div className={''}>
                                                        <SlideBuilder
                                                            slide={slide}
                                                            disabled
                                                            isScaledDown
                                                        />
                                                    </div>

                                                    {/* {activeSlideComponent?.id ===
                                                        slide.id && (
                                                        <div
                                                            className="absolute -top-7 right-0 cursor-pointer rounded-md bg-white p-2 shadow-bubble"
                                                            onClick={(e: any) => {
                                                                e.preventDefault();
                                                                e.stopPropagation();
                                                                deleteActiveSlide();
                                                            }}
                                                        >
                                                            <DeleteIcon
                                                                width={24}
                                                                height={24}
                                                            />
                                                        </div>
                                                    )} */}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <></>
                            )}
                        </div>
                    </ScrollArea>

                    <div className="border-t border-t-black-400 px-2 pt-4">
                        <div
                            className={cn(
                                ' mb-3 rounded-lg border border-transparent px-2 pb-2 pt-1',
                                activeSlideComponent?.id === 'thank-you-page' &&
                                    'border-pink-500'
                            )}
                        >
                            <div className="p2-new mb-1 font-medium text-black-700">
                                End
                            </div>
                            <div
                                className={cn(
                                    ' relative flex !aspect-video cursor-pointer items-center justify-center overflow-clip rounded-lg border bg-white'
                                )}
                                onClick={() => {
                                    setActiveSlideComponent({
                                        id: 'thank-you-page',
                                        index: -20
                                    });
                                }}
                            >
                                <ThankYouSlide disabled />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <AnimatePresence initial={false} mode="wait">
                {!(
                    activeSlideComponent?.id === 'welcome-page' ||
                    activeSlideComponent?.id === 'thank-you-page'
                ) &&
                    navbarState.insertClicked && (
                        <motion.div
                            key="field-options"
                            initial={{ opacity: 0, x: '-100%' }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: '-100%' }}
                            transition={{ duration: 0.3 }}
                            id="fields-option"
                            className=" absolute z-10 h-body-content w-[240px] overflow-y-auto overflow-x-hidden bg-white "
                        >
                            <div className="grid grid-cols-2">
                                {Array.isArray(formFieldsList) &&
                                    formFieldsList.length &&
                                    formFieldsList.map(
                                        (
                                            field: {
                                                name: string;
                                                type: FieldTypes;
                                                icon: ReactNode;
                                            },
                                            index: number
                                        ) => {
                                            return (
                                                <div
                                                    onClick={() =>
                                                        handleAddField(field)
                                                    }
                                                    key={index}
                                                    className="flex h-[120px] w-[120px] cursor-grab flex-col items-center justify-center gap-1 border-[1px] border-black-300 text-black-600"
                                                >
                                                    {field.icon}
                                                    <span className="text-xs">
                                                        {' '}
                                                        {field.name}
                                                    </span>
                                                </div>
                                            );
                                        }
                                    )}
                            </div>
                        </motion.div>
                    )}
            </AnimatePresence>
        </>
    );
}
