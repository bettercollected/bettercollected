'use client';

import { useEffect } from 'react';

import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import FormSlide from '@app/views/organism/Form/FormSlide';
import ThankyouPage from '@app/views/organism/Form/ThankyouPage';
import WelcomePage from '@app/views/organism/Form/WelcomePage';

export default function ResponsePage({
    searchParams
}: {
    searchParams: { responseId?: string };
}) {
    const { standardForm } = useStandardForm();
    const { formResponse, setFormResponse } = useFormResponse();

    useEffect(() => {
        if (searchParams.responseId)
            console.log('Fetch response for Id:', searchParams.responseId);
    }, [searchParams.responseId]);
    return (
        <div className="h-screen w-screen">
            <ScrollArea className="overfloe-y-auto flex h-full w-full flex-col">
                <div className="p-4">
                    <div className="aspect-video w-full overflow-hidden rounded-xl border border-2 border-black-400">
                        <WelcomePage />
                    </div>
                </div>
                {standardForm?.fields?.map((_, index) => {
                    return (
                        <div className="p-4">
                            <div className="aspect-video w-full overflow-hidden rounded-xl border border-2 border-black-400 ">
                                <FormSlide index={index} />
                            </div>
                        </div>
                    );
                })}
                <div className="p-4">
                    <div className="aspect-video w-full overflow-hidden rounded-xl border border-2 border-black-400 ">
                        <ThankyouPage />
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
