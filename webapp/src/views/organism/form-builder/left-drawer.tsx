import { ReactNode } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';
import { slideHasLogic } from '@app/utils/conditional-logic';
import { LogicOutlinedIcon } from '@Components/icons/logic-outlined-icon';

import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

import AddSlidePopover from './add-slide/add-slide-popover';
import SlideOptions from './slide-options';

/**
 * One grammar for every page in the rail — welcome, content and thank-you pages
 * all render as the same labelled schematic card. The rail used to speak three
 * dialects (icon rows for the ends, cards for the middle), which made "a page"
 * read as three different things.
 */
function RailPageItem({
    label,
    chips,
    menu,
    selected,
    onSelect,
    primaryText,
    secondaryText
}: {
    label: string;
    chips?: ReactNode;
    menu?: ReactNode;
    selected: boolean;
    onSelect: () => void;
    primaryText?: string;
    secondaryText: string;
}) {
    return (
        <div className={cn('group relative flex flex-col gap-1.5 px-4 py-3', selected && 'bg-black-100')}>
            <div className="flex w-full items-center justify-between">
                <div className={cn('flex items-center gap-1 text-[10px] font-medium', selected ? 'text-black-800' : 'text-black-600')}>
                    {label}
                    {chips}
                </div>
                {menu}
            </div>
            <div
                role="button"
                tabIndex={0}
                className={cn(
                    'flex min-h-[64px] w-full cursor-pointer flex-col justify-center gap-1 overflow-hidden rounded-lg border bg-white px-3 py-2 transition-colors',
                    selected ? 'border-[#2456CC] shadow-[0_0_0_1px_#2456CC]' : 'border-black-300 hover:border-black-400'
                )}
                onClick={onSelect}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') onSelect();
                }}
            >
                {primaryText ? <span className="text-black-800 line-clamp-2 text-[11px] font-medium leading-snug">{primaryText}</span> : null}
                <span className="text-black-500 text-[10px]">{secondaryText}</span>
            </div>
        </div>
    );
}

function LeftDrawer({ formFields, activeSlideComponent }: { formFields: Array<StandardFormFieldDto>; activeSlideComponent: any }) {
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { formState } = useFormState();
    const Slides = formFields;

    return (
        <>
            <div onClick={() => setActiveFieldComponent(null)} id="slides-preview" className="h-body-content border-r-black-300 flex w-[200px] flex-col overflow-y-auto overflow-x-hidden border-r bg-white">
                <div className="border-b-black-300 flex w-full items-center justify-between border-b p-5">
                    <span className="h4-new text-black-700 font-medium">Pages</span>
                    <AddSlidePopover />
                </div>
                <div className="flex flex-1 flex-col overflow-auto">
                    <div className="border-b-black-300 border-b pb-1">
                        <RailPageItem
                            label="Welcome"
                            selected={activeSlideComponent?.id === 'welcome-page'}
                            onSelect={() => setActiveSlideComponent({ id: 'welcome-page', index: -10 })}
                            primaryText={formState.welcomePage?.title || formState.title || undefined}
                            secondaryText="Welcome screen"
                        />
                    </div>
                    <ScrollArea className="max-h-pages-container flex-1 overflow-y-auto">
                        <div className="flex w-[200px] flex-col py-1">
                            {Array.isArray(Slides) && Slides.length ? (
                                Slides.map((slide, index) => {
                                    const questionCount = slide?.properties?.fields?.length ?? 0;
                                    return (
                                        <div key={slide.id} id={slide.id}>
                                            <RailPageItem
                                                label={`Page ${index + 1}`}
                                                chips={
                                                    slideHasLogic(slide) ? (
                                                        <span title="This page has logic" className="inline-flex items-center gap-0.5 rounded bg-[#E9EFFC] px-1 py-[1px] text-[9px] font-semibold text-[#2456CC]">
                                                            <LogicOutlinedIcon className="h-2.5 w-2.5" />
                                                            Logic
                                                        </span>
                                                    ) : undefined
                                                }
                                                menu={<SlideOptions slideIndex={slide.index} />}
                                                selected={activeSlideComponent?.id === slide.id}
                                                onSelect={() => setActiveSlideComponent({ id: slide.id, index })}
                                                primaryText={questionCount ? extractTextfromJSON(slide.properties!.fields![0]) : undefined}
                                                secondaryText={questionCount ? `${questionCount} question${questionCount === 1 ? '' : 's'}` : 'No questions yet'}
                                            />
                                        </div>
                                    );
                                })
                            ) : (
                                <></>
                            )}
                        </div>
                    </ScrollArea>

                    <div className="border-t-black-300 border-t pt-1">
                        <RailPageItem
                            label="Thank you"
                            selected={activeSlideComponent?.id === 'thank-you-page'}
                            onSelect={() => setActiveSlideComponent({ id: 'thank-you-page', index: -20 })}
                            primaryText={formState.thankyouPage?.[0]?.message || undefined}
                            secondaryText="Ending"
                        />
                    </div>
                </div>
            </div>
        </>
    );
}

export default LeftDrawer;
