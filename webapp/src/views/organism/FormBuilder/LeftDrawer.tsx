import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { useNavbarState } from '@app/store/jotai/navbar';

import AddSlidePopover from './AddSlide/AddSlidePopover';
import SlideBuilder from './SlideBuilder';
import SlideOptions from './SlideOptions';
import ThankYouSlide from './ThankYouPage';
import WelcomeSlide from './WelcomePage';
import { AnimatePresence } from 'framer-motion';

function LeftDrawer({ formFields, activeSlideComponent }: { formFields: Array<StandardFormFieldDto>; activeSlideComponent: any }) {
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const Slides = formFields;

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
                            <div className="border-black-200 h-[30px] w-[54px] overflow-hidden rounded-lg border">
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
                                            <div key={slide.id} className="border-black-200 !aspect-video w-full overflow-hidden rounded-lg border">
                                                <div
                                                    role="button"
                                                    className={cn('shadow-slide  flex  cursor-pointer items-center justify-center overflow-hidden ')}
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
                            <div className="border-black-200 h-[30px] w-[54px] overflow-hidden rounded-lg border">
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
        </>
    );
}

export default LeftDrawer;
