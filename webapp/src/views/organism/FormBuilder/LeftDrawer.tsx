import { ReactNode } from 'react';

import { AnimatePresence, motion } from 'framer-motion';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { FieldTypes, StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Checkbox } from '@app/shadcn/components/ui/checkbox';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useNavbarState } from '@app/store/jotai/navbar';

import AddSlidePopover from './AddSlide/AddSlidePopover';
import SlideBuilder from './SlideBuilder';
import SlideOptions from './SlideOptions';
import ThankYouSlide from './ThankYouPage';
import WelcomeSlide from './WelcomePage';

function LeftDrawer({ formFields, activeSlideComponent }: { formFields: Array<StandardFormFieldDto>; activeSlideComponent: any }) {
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { addField, addSlide, getNewField } = useFormFieldsAtom();
    const Slides = formFields;
    const { navbarState, setNavbarState } = useNavbarState();
    const fieldId = v4();

    function checkIfInputFieldExistsInSlide(slide: StandardFormFieldDto) {
        if (!slide?.properties?.fields?.length) return false;
        return slide?.properties?.fields?.some((field) => field.type && V2InputFields.includes(field.type));
    }

    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add fields');
            return;
        }
        const slideIndex = activeSlideComponent.index < 0 ? formFields.length - 1 : activeSlideComponent.index;
        const slide = formFields[slideIndex];
        const slideId = checkIfInputFieldExistsInSlide(slide) && navbarState.multiplePages ? v4() : slide.id;
        if ((checkIfInputFieldExistsInSlide(slide) && navbarState.multiplePages) || formFields.length === 0) {
            addSlide({
                id: slideId,
                index: formFields.length,
                type: FieldTypes.SLIDE,
                properties: {
                    layout: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                    fields: [getNewField(field, fieldId, formFields.length)]
                },
                imageUrl: 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2defaultImage.png'
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
            <div onClick={() => setActiveFieldComponent(null)} id="slides-preview" className="h-body-content border-r-black-300 flex w-[200px] flex-col overflow-y-auto overflow-x-hidden border-r bg-white">
                <div className="border-b-black-400 flex w-full items-center justify-between border-b p-5">
                    <span className="h4-new text-black-700 font-medium">Pages</span>
                    <AddSlidePopover />
                </div>
                <div className=" justify- flex flex-1 flex-col overflow-auto">
                    <div className="border-b-black-400 relative overflow-hidden border-b">
                        <div
                            className={cn(' flex h-[62px] cursor-pointer flex-row-reverse items-center justify-center gap-2', activeSlideComponent?.id === 'welcome-page' && 'bg-black-100')}
                            onClick={() => {
                                setActiveSlideComponent({
                                    id: 'welcome-page',
                                    index: -10
                                });
                            }}
                        >
                            {activeSlideComponent.id === 'welcome-page' && <div className="absolute bottom-0 left-0 top-0 h-full w-1" style={{ background: 'blue' }}></div>}
                            <div className=" text-black-900 mb-1 !text-[10px] font-medium">Welcome Page</div>
                            <div className="h-[30px] w-[54px] overflow-hidden rounded-lg">
                                <div
                                    className={cn('shadow-slide flex !aspect-video flex-1 cursor-pointer items-center justify-center overflow-hidden rounded bg-white')}
                                    style={{
                                        height: '1080px',
                                        width: '1920px',
                                        transformOrigin: 'top left',
                                        scale: 0.02815
                                    }}
                                >
                                    <div className="pointer-events-none h-full w-full">
                                        <WelcomeSlide disabled />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <ScrollArea className="max-h-pages-container flex-1  overflow-y-auto">
                        <div className="flex  w-[200px]  flex-col gap-2">
                            {Array.isArray(Slides) && Slides.length ? (
                                Slides.map((slide, index) => {
                                    return (
                                        <div key={slide.id} id={slide.id} className={cn('group relative flex flex-col gap-2 px-4 py-4 pl-6', activeSlideComponent?.id === slide.id && '!bg-black-100')}>
                                            <div className="flex w-full justify-between">
                                                <div className="text-black-700 mb-1 text-[10px] font-medium">Page {index + 1}</div>
                                                <SlideOptions slideIndex={slide.index} />
                                            </div>
                                            <div key={slide.id} className={cn('h-[102px]')}>
                                                <div
                                                    role="button"
                                                    className={cn('shadow-slide flex !aspect-video cursor-pointer items-center justify-center overflow-hidden border')}
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
                                                        scale: 0.113
                                                    }}
                                                >
                                                    <div className="pointer-events-none h-full w-full">
                                                        <SlideBuilder slide={slide} disabled isScaledDown />
                                                    </div>
                                                </div>
                                            </div>
                                            {activeSlideComponent.id === slide.id && <div className="absolute bottom-0 left-0 top-0 h-full w-1" style={{ background: 'blue' }}></div>}
                                        </div>
                                    );
                                })
                            ) : (
                                <></>
                            )}
                        </div>
                    </ScrollArea>

                    <div className="border-t-black-400 relative border-t">
                        {activeSlideComponent.id === 'thank-you-page' && <div className="absolute bottom-0 left-0 top-0 h-full w-1" style={{ background: 'blue' }}></div>}

                        <div
                            className={cn(' flex h-[62px] cursor-pointer flex-row-reverse items-center justify-center gap-2 rounded-lg border border-transparent ', activeSlideComponent?.id === 'thank-you-page' && 'bg-black-100')}
                            onClick={() => {
                                setActiveSlideComponent({
                                    id: 'thank-you-page',
                                    index: -20
                                });
                            }}
                        >
                            <div className=" text-black-900 mb-1 !text-[10px] font-medium">Thank You Page</div>
                            <div className="h-[30px] w-[54px] overflow-hidden rounded-lg">
                                <div
                                    className={cn('shadow-slide flex !aspect-video flex-1 cursor-pointer items-center justify-center overflow-hidden rounded bg-white')}
                                    style={{
                                        height: '1080px',
                                        width: '1920px',
                                        transformOrigin: 'top left',
                                        scale: 0.02815
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
            </div>
            <AnimatePresence initial={false} mode="wait">
                {navbarState.insertClicked && (
                    <motion.div key="field-options" initial={{ opacity: 1, x: '-100%' }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 1, x: '-100%' }} transition={{ duration: 0.3 }} id="fields-option" className="absolute z-10">
                        <div className="border-r-black-300 h-body-content w-[240px] border-r bg-white ">
                            <div className=" border-black-300 bg-new-white-200 sticky top-0 flex w-full flex-col items-start gap-2 border-b-[1px] p-4">
                                <div className="flex gap-2">
                                    <input
                                        type="radio"
                                        id="multi-page"
                                        checked={navbarState.multiplePages}
                                        name="multi-page"
                                        className="h-5 w-5 focus:ring-0 focus:ring-offset-0"
                                        onClick={(e: any) =>
                                            setNavbarState({
                                                ...navbarState,
                                                multiplePages: e.target.value === 'True'
                                            })
                                        }
                                        value={'True'}
                                    />
                                    <label htmlFor="multi-page" className="p4-new text-black-700 cursor-pointer">
                                        Insert in new page
                                    </label>
                                </div>
                                <div className="flex gap-2">
                                    <input
                                        id="single-page"
                                        type="radio"
                                        onClick={(e: any) =>
                                            setNavbarState({
                                                ...navbarState,
                                                multiplePages: e.target.value === 'True'
                                            })
                                        }
                                        checked={!navbarState.multiplePages}
                                        name="multi-page"
                                        value={'False'}
                                        className="h-5 w-5 focus:ring-0 focus:ring-offset-0"
                                    />
                                    <label htmlFor="single-page" className="p4-new text-black-700 cursor-pointer">
                                        Insert in current page
                                    </label>
                                </div>
                                {/* <div className="h-5 w-5">
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
                                    <h1 className="text-black-800 text-sm font-semibold">Multi-Page Form</h1>
                                    <span className="text-black-600 text-xs">Whenever your insert elements add in new page</span>
                                </div> */}
                            </div>
                            <ScrollArea className="h-full overflow-y-auto overflow-x-hidden">
                                <div className="mb-24 grid grid-cols-2">
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
                                                        onClick={() => handleAddField(field)}
                                                        key={index}
                                                        className="border-black-300 text-black-600 hover:bg-black-100 hover:text-black-900 flex h-[120px] w-[120px] cursor-grab flex-col items-center justify-center gap-2 border-b-[1px] border-r-[1px]"
                                                    >
                                                        {field.icon}
                                                        <span className="text-xs"> {field.name}</span>
                                                    </div>
                                                );
                                            }
                                        )}
                                </div>
                            </ScrollArea>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}

export default LeftDrawer;
