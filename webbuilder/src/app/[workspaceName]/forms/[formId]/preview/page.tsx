'use client';

import { useEffect } from 'react';

import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import useWorkspace from '@app/store/jotai/workspace';
import { useGetFormResponseQuery } from '@app/store/redux/formApi';
import FormSlide from '@app/views/organism/Form/FormSlide';
import ThankyouPage from '@app/views/organism/Form/ThankyouPage';
import WelcomePage from '@app/views/organism/Form/WelcomePage';

export default function ResponsePage({
    searchParams
}: {
    searchParams: { responseId?: string };
}) {
    const { standardForm } = useStandardForm();
    const { setFormResponse } = useFormResponse();
    const { workspace } = useWorkspace();
    const { data } = useGetFormResponseQuery(
        {
            workspaceId: workspace.id,
            responseId: searchParams?.responseId
        },
        {
            skip: !(workspace.id && searchParams?.responseId)
        }
    );

    useEffect(() => {
        if (data?.response?.responseId) {
            setFormResponse({
                formId: standardForm.formId,
                currentSlide: 0,
                currentField: 0,
                prevActiveField: -1,
                answers: data?.response?.answers
            });
        }
    }, [data?.response?.responseId]);
    return (
        <div className="h-screen w-screen">
            <ScrollArea className="overfloe-y-auto  flex h-full w-full flex-col">
                <div className="pointer-events-none">
                    <div className="p-4">
                        <div className="aspect-video w-full overflow-hidden rounded-xl border border-black-400">
                            <WelcomePage />
                        </div>
                    </div>
                    {standardForm?.fields?.map((_, index) => {
                        return (
                            <div className="p-4" key={index}>
                                <div className="aspect-video w-full overflow-hidden rounded-xl border border-black-400 ">
                                    <FormSlide index={index} />
                                </div>
                            </div>
                        );
                    })}
                    <div className="p-4">
                        <div className="aspect-video w-full overflow-hidden rounded-xl border border-black-400 ">
                            <ThankyouPage />
                        </div>
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
