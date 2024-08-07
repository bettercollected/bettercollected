import React from 'react';

import FormRenderer from '@app/Components/Form/renderer/form-renderer';
import { StandardFormDto } from '@app/models/dtos/form';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';
import FormSlidePreview from '@app/views/organism/FormPreview/FormSlidePreview';

export const FormTabContent = ({ form }: { form: StandardFormDto }) => {
    const getContainerWidth = () => {
        if (typeof window !== 'undefined') {
            const windowWidth = window.innerWidth;
            let padding = 5 * 4 * 2;
            if (windowWidth > 768) padding = 10 * 4 * 2;
            if (windowWidth > 1024) padding = 28 * 4 * 2 + 4 * 4;
            let containerWidth = windowWidth - padding;
            if (windowWidth > 1024) containerWidth = containerWidth / 2;
            return containerWidth;
        }
        return 0;
    };
    const getPreviewStyles = () => {
        const containerWidth = getContainerWidth();
        return {
            scale: (containerWidth / 1440).toString(),
            transformOrigin: 'top left'
        };
    };

    if (form?.builderVersion === 'v2') {
        return (
            <>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className=" border-black-300 relative aspect-video overflow-hidden rounded-lg rounded-md border" style={{ width: getContainerWidth() }}>
                        <div className=" pointer-events-none h-[810px] w-[1440px]" style={getPreviewStyles()}>
                            <LayoutWrapper showDesktopLayout theme={form?.theme} disabled layout={form.welcomePage?.layout} imageUrl={form?.welcomePage?.imageUrl}>
                                <WelcomePage isPreviewMode theme={form?.theme} welcomePageData={form?.welcomePage} />
                            </LayoutWrapper>
                        </div>
                    </div>
                    {form?.fields?.map((slide) => (
                        <div className="mb-2 flex w-min cursor-pointer flex-col  rounded-lg border border-transparent" key={slide?.id}>
                            <div className="border-black-300 relative aspect-video overflow-hidden rounded-md border" style={{ width: getContainerWidth() }}>
                                <div className="pointer-events-none h-[810px] w-[1440px]" style={getPreviewStyles()}>
                                    <FormSlidePreview slide={slide} theme={form.theme} />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </>
        );
    }
    return (
        <div className="max-w-screen flex w-full items-center overflow-x-auto rounded bg-white ">
            <FormRenderer form={form} enabled={false} isDisabled={true} />
        </div>
    );
};
