import { ReactNode } from 'react';

import { AnimatePresence, motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Checkbox } from '@app/shadcn/components/ui/checkbox';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useNavbarState } from '@app/store/jotai/navbar';

import AddSlidePopover from './AddSlide/AddSlidePopover';
import SlideBuilder from './SlideBuilder';
import SlideOptions from './SlideOptions';
import ThankYouSlide from './ThankYouPage';
import WelcomeSlide from './WelcomePage';

export default function LeftDrawer({}: {}) {
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { formFields, addField, addSlide, getNewField } = useFormFieldsAtom();
    const Slides = formFields;
    const { navbarState, setNavbarState } = useNavbarState();
    const fieldId = v4();

    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add fields');
            return;
        }
        const slideIndex =
            activeSlideComponent.index < 0
                ? formFields.length - 1
                : activeSlideComponent.index;
        const slide = formFields[slideIndex];
        const slideId = navbarState.multiplePages ? v4() : slide.id;
        if (navbarState.multiplePages || formFields.length === 0) {
            addSlide({
                id: slideId,
                index: formFields.length,
                type: FieldTypes.SLIDE,
                properties: {
                    layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                    fields: [getNewField(field, fieldId, slideIndex + 1)]
                },
                imageUrl:
                    'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png'
            });
            setActiveSlideComponent({ id: slideId, index: formFields.length });
            window.setTimeout(function () {
                const slideElement = document.getElementById(slideId);
                slideElement?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'end'
                });
            }, 500);
        } else {
            addField(getNewField(field, fieldId, slideIndex), slideIndex);
            setActiveSlideComponent({
                id: slideId,
                index: slideIndex
            });
            window.setTimeout(function () {
                const fieldElement = document.getElementById(`scroll-field-${fieldId}`);
                fieldElement?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'end'
                });
            }, 500);
        }
        setNavbarState({ ...navbarState, insertClicked: false });
        setActiveFieldComponent({
            id: fieldId,
            index: (formFields[slideIndex]?.properties?.fields?.length ?? 1) - 1
        });
    };

    return (
        <>
            <div
                onClick={() => setActiveFieldComponent(null)}
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
                                'mb-6 h-32 rounded-lg border border-transparent px-2 pb-2 pt-1',
                                activeSlideComponent?.id === 'welcome-page' &&
                                    'border-pink-500'
                            )}
                        >
                            <div className=" mb-1 !text-[10px] font-medium text-black-700">
                                Welcome Screen
                            </div>
                            <div
                                className={cn(
                                    'flex !aspect-video cursor-pointer items-center justify-center overflow-auto rounded-lg bg-white shadow-slide'
                                )}
                                onClick={() => {
                                    setActiveSlideComponent({
                                        id: 'welcome-page',
                                        index: -10
                                    });
                                }}
                                style={{
                                    height: '1080px',
                                    width: '1920px',
                                    transformOrigin: 'top left',
                                    scale: 0.086
                                }}
                            >
                                <div className="pointer-events-none h-full w-full">
                                    <WelcomeSlide disabled />
                                </div>
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
                                            id={slide.id}
                                            className={cn(
                                                'group flex flex-col gap-2 rounded-lg border border-transparent px-2 pt-1',
                                                activeSlideComponent?.id === slide.id &&
                                                    '!border-pink-500'
                                            )}
                                        >
                                            <div className="flex w-full justify-between">
                                                <div className="mb-1 text-[10px] font-medium text-black-700">
                                                    Page {index + 1}
                                                </div>
                                                <SlideOptions
                                                    slideIndex={slide.index}
                                                />
                                            </div>
                                            <div
                                                key={slide.id}
                                                className={cn('h-[102px]')}
                                            >
                                                <div
                                                    role="button"
                                                    className={cn(
                                                        'flex !aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-lg border shadow-slide'
                                                    )}
                                                    onClick={() => {
                                                        setActiveSlideComponent({
                                                            id: slide.id,
                                                            index
                                                        });
                                                    }}
                                                    style={{
                                                        height: '810px',
                                                        width: '1440px',
                                                        transformOrigin: 'top left',
                                                        scale: 0.115
                                                    }}
                                                >
                                                    <div className="pointer-events-none h-full w-full">
                                                        <SlideBuilder
                                                            slide={slide}
                                                            disabled
                                                            isScaledDown
                                                        />
                                                    </div>
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
                                ' mb-3 h-32 rounded-lg border border-transparent px-2 pb-2 pt-1',
                                activeSlideComponent?.id === 'thank-you-page' &&
                                    'border-pink-500'
                            )}
                        >
                            <div className="mb-1 text-[10px] font-medium text-black-700">
                                End Screen
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
                                style={{
                                    height: '1080px',
                                    width: '1920px',
                                    transformOrigin: 'top left',
                                    scale: 0.086
                                }}
                            >
                                <div className="pointer-events-none h-full w-full">
                                    <ThankYouSlide disabled />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <AnimatePresence initial={false} mode="wait">
                {navbarState.insertClicked && (
                    <motion.div
                        key="field-options"
                        initial={{ opacity: 1, x: '-100%' }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 1, x: '-100%' }}
                        transition={{ duration: 0.3 }}
                        id="fields-option"
                        className="absolute z-10"
                    >
                        <ScrollArea className="h-body-content w-[240px] overflow-y-auto overflow-x-hidden border-r border-r-black-300 bg-white ">
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
                                                    className="flex h-[120px] w-[120px] cursor-grab flex-col items-center justify-center gap-2 border-b-[1px] border-r-[1px] border-black-300 text-black-600 hover:bg-black-100 hover:text-black-900"
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
                        </ScrollArea>
                        <div className="absolute bottom-0 flex w-full items-start gap-2 bg-white p-4 shadow-v2">
                            <div className="h-5 w-5">
                                <Checkbox
                                    checked={navbarState.multiplePages}
                                    onCheckedChange={(checked: boolean) =>
                                        setNavbarState({
                                            ...navbarState,
                                            multiplePages: checked
                                        })
                                    }
                                />
                            </div>
                            <div className="flex flex-col justify-center gap-2">
                                <h1 className="text-sm font-semibold text-black-800">
                                    Multi-Page Form
                                </h1>
                                <span className="text-xs text-black-600">
                                    Whenever your insert elements add in new page
                                </span>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
