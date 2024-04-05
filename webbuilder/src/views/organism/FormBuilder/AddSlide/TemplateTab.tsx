import React, { useState } from 'react';

import { ChevronLeft } from 'lucide-react';

import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useGetTemplatesQuery } from '@app/store/redux/templateApi';
import { IFormTemplateDto } from '@app/store/redux/types';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import FormSlidePreview from '@app/views/organism/FormPreview/FormSlidePreview';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';


export default function TemplateTab({ closePopover }: { closePopover: () => void }) {
    const [selectedTemplate, setSelectedTemplate] = useState<
        IFormTemplateDto | undefined
    >();

    const { addSlideFormTemplate } = useFormFieldsAtom();
    const { theme } = useFormState();
    const { data: templates } = useGetTemplatesQuery({ v2: true });

    return (
        <>
            {selectedTemplate && (
                <>
                    <div className="mb-2 flex items-center gap-2">
                        <ChevronLeft
                            size={24}
                            className="cursor-pointer hover:bg-black-100"
                            onClick={() => {
                                setSelectedTemplate(undefined);
                            }}
                        />
                        <span className="text-xs font-medium ">
                            {selectedTemplate?.title || 'Untitled'}
                        </span>
                    </div>
                    <ScrollArea className="h-[495px] overflow-auto">
                        <div className="flex !h-full w-full flex-row flex-wrap gap-2 overflow-auto">
                            {selectedTemplate?.fields?.map((slide) => (
                                <div
                                    onClick={() => {
                                        addSlideFormTemplate(slide);
                                        closePopover();
                                    }}
                                    className="mb-2 flex w-min cursor-pointer flex-col  rounded-lg border border-transparent p-1 hover:border-pink-500"
                                    key={slide?.id}
                                >
                                    <div className="relative aspect-video w-[160px] overflow-hidden rounded-md border border-black-300">
                                        <div
                                            className="pointer-events-none h-[720px] w-[1280px] scale-[0.125]"
                                            style={{ transformOrigin: 'top left' }}
                                        >
                                            <FormSlidePreview
                                                slide={slide}
                                                theme={theme}
                                            />
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </>
            )}
            {!selectedTemplate && (
                <>
                    <div className="mb-2 flex h-6 items-center text-xs font-medium">
                        Templates
                    </div>
                    <ScrollArea className="h-[495px] overflow-auto">
                        <div className="flex w-full flex-row flex-wrap ">
                            {templates?.map((template) => (
                                <div
                                    className="mb-2 flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500"
                                    key={template?.id}
                                    onClick={() => {
                                        setSelectedTemplate(template);
                                    }}
                                >
                                    <div className="relative aspect-video w-[160px] overflow-hidden rounded-md border border-black-300">
                                        <div
                                            className="pointer-events-none h-[810px] w-[1440px] scale-[0.116666667]"
                                            style={{ transformOrigin: 'top left' }}
                                        >
                                            <LayoutWrapper
                                                theme={theme}
                                                disabled
                                                layout={template.welcomePage?.layout}
                                                imageUrl={
                                                    template?.welcomePage?.imageUrl
                                                }
                                            >
                                                <WelcomePage
                                                    isPreviewMode
                                                    welcomePageData={
                                                        template?.welcomePage
                                                    }
                                                />
                                            </LayoutWrapper>
                                        </div>
                                    </div>
                                    <div className="p2-new mt-2 !font-medium">
                                        {template.title}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </ScrollArea>
                </>
            )}
        </>
    );
}
