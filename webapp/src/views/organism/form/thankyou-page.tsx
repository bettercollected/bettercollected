"use client";
import Link from 'next/link';

import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { resolvePipesInText } from '@app/utils/answer-piping';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';
import { Copy } from 'lucide-react';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const submissionUrl = window.PUBLIC_CONFIG?.HTTP_SCHEME + window.PUBLIC_CONFIG?.FORM_DOMAIN + '/' + workspace.workspaceName;
    const { responderId } = useResponderState();
    const [_, copyToClipboard] = useCopyToClipboard();
    const { formResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();

    function getThankYouMessage() {
        const message = standardForm?.thankyouPage?.[0]?.message ? standardForm?.thankyouPage?.[0]?.message : formResponse.anonymize ? 'Your response is anonymously submitted.' : 'Your response is successfully submitted.';
        // Thank-you text supports text-token piping: "Thanks, {{field:<id>}}!"
        return resolvePipesInText(message, { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues });
    }

    // The heading is customizable (and pipeable) like the message; the classic
    // greeting stays as the default for forms that never set one.
    function getThankYouTitle() {
        const title = standardForm?.thankyouPage?.[0]?.title;
        if (!title) return 'Thank You! 🎉';
        return resolvePipesInText(title, { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues });
    }

    const handleOnCopy = (copyValue: string) => {
        copyToClipboard(copyValue);
        toast({
            description: 'Copied'
        });
    };
    // Forms created outside the builder (API/MCP) may have no thank-you page
    // at all — every read below must survive null/[] (the `!` + index here
    // crashed the post-submit screen with "Cannot read properties of null").
    const thankyouPage = standardForm?.thankyouPage?.[0];
    return (
        <div className={cn('flex h-full w-full flex-col justify-center bg-inherit', thankyouPage?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'items-start' : 'items-center')}>
            <UserAvatarDropDown disabled />
            <div className=" flex h-full w-full max-w-[800px] flex-col justify-between">
                <div className="flex">
                    <span className="text-[40px] font-bold leading-[48px]">{getThankYouTitle()}</span>
                </div>
                <div className="p2-new text-black-700 mt-4">{getThankYouMessage()}</div>
                {thankyouPage?.buttonText && (
                    <Button style={{ background: standardForm.theme?.secondary }} className="mt-14">
                        <Link href={isPreviewMode ? '' : thankyouPage.buttonLink || 'https://bettercollected.com'} target="_blank" referrerPolicy="no-referrer">
                            {thankyouPage.buttonText}
                        </Link>
                    </Button>
                )}
                {auth.id && standardForm.settings?.showSubmissionNumber && (
                    <div className="p2-new mt-10 flex max-w-[400px] flex-col gap-2 rounded-lg bg-white/50 p-4 ">
                        <div className="flex flex-row justify-between">
                            <span className="p3-new text-black-800">Submission Number</span>
                            <Link href={isPreviewMode ? '' : submissionUrl} className="text-blue-500">
                                See all your submissions
                            </Link>
                        </div>
                        <span className="p4-new text-black-700">Use this submission number to view or request deletion of this response.</span>
                        <div className="bg-black-100/50 flex justify-between rounded-lg px-4 py-2">
                            <span className="p4-new text-black-700">{responderId}</span>
                            <Copy
                                className="text-brand-500 h-4 w-4 cursor-pointer"
                                onClick={() => {
                                    responderId && handleOnCopy(responderId);
                                }}
                            />
                        </div>
                    </div>
                )}
                {/* Attribution moved into the trust strip — the form's single
                    footer. A second floating "Powered by" here sat underneath
                    the fixed strip and the two overlapped. */}
            </div>
        </div>
    );
}
