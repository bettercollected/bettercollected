import React, { useState } from 'react';

import { ChevronLeft } from 'lucide-react';

import { useGetTemplatesQuery } from '@app/store/redux/templateApi';
import { IFormTemplateDto } from '@app/store/redux/types';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import FormSlidePreview from '@app/views/organism/FormPreview/FormSlidePreview';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';


export default function TemplateTab({ closePopover }: { closePopover: () => void }) {
    const [selectedTemplate, setSelectedTemplate] = useState<
        IFormTemplateDto | undefined
    >();
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
                    <div className="flex w-full flex-row flex-wrap gap-2 ">
                        {selectedTemplate?.fields?.map((slide) => (
                            <div
                                className="flex cursor-pointer flex-col  rounded-lg border border-transparent p-1 hover:border-pink-500"
                                key={slide?.id}
                            >
                                <div className="relative h-[94px] w-[160px] overflow-hidden rounded-md">
                                    <div
                                        className="pointer-events-none h-[810px] w-[1440px] scale-[0.116666667]"
                                        style={{ transformOrigin: 'top left' }}
                                    >
                                        <FormSlidePreview
                                            slide={slide}
                                            theme={selectedTemplate.theme}
                                        />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </>
            )}
            {!selectedTemplate && (
                <>
                    <div className="mb-2 text-xs font-medium ">Templates</div>
                    <div className="flex w-full flex-row flex-wrap ">
                        {templates?.map((template) => (
                            <div
                                className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500"
                                key={template?.id}
                                onClick={() => {
                                    setSelectedTemplate(template);
                                }}
                            >
                                <div className="relative h-[94px] w-[168px] overflow-hidden rounded-md">
                                    <div
                                        className="pointer-events-none h-[810px] w-[1440px] scale-[0.116666667]"
                                        style={{ transformOrigin: 'top left' }}
                                    >
                                        <LayoutWrapper
                                            theme={template?.theme}
                                            disabled
                                            layout={template.welcomePage?.layout}
                                            imageUrl={template?.welcomePage?.imageUrl}
                                        >
                                            <WelcomePage
                                                isPreviewMode
                                                welcomePageData={template?.welcomePage}
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
                </>
            )}
        </>
    );
}
