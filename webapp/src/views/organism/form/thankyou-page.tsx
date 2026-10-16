'use client';
import Link from 'next/link';

import { Copy } from 'lucide-react';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { resolvePipesInText } from '@app/utils/answer-piping';
import UserAvatarDropDown from '@app/views/molecules/user-avatar-dropdown';
import { FORM_COLUMN, columnPlacementClass, greetingAlignClass } from '@app/views/organism/layout/form-column';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectResponderForm);
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
        <>
            <UserAvatarDropDown disabled />
            {/* Same column, alignment and vertical placement as the welcome
                page (form-column.ts, layout-wrapper.tsx). */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(thankyouPage?.layout), 'flex flex-col bg-inherit pt-6', greetingAlignClass(thankyouPage?.layout))} data-testid="thankyou-column">
                <h1 className="text-[32px] leading-[40px] font-bold text-balance [overflow-wrap:anywhere] sm:text-[40px] sm:leading-[48px]">{getThankYouTitle()}</h1>
                <p className="p2-new mt-4 max-w-[60ch] text-pretty text-black-700">{getThankYouMessage()}</p>
                {thankyouPage?.buttonText && (
                    <Button flat style={{ background: standardForm.theme?.secondary }} className="mt-8 rounded-[8px]">
                        <Link href={isPreviewMode ? '' : thankyouPage.buttonLink || 'https://bettercollected.com'} target="_blank" referrerPolicy="no-referrer">
                            {thankyouPage.buttonText}
                        </Link>
                    </Button>
                )}
                {auth.id && standardForm.settings?.showSubmissionNumber && (
                    <div className="p2-new mt-8 flex w-full max-w-[400px] flex-col gap-2 rounded-[8px] bg-white/50 p-4 text-left">
                        <div className="flex flex-row justify-between">
                            <span className="p3-new text-black-800">Submission Number</span>
                            <Link href={isPreviewMode ? '' : submissionUrl} className="text-blue-500">
                                See all your submissions
                            </Link>
                        </div>
                        <span className="p4-new text-black-700">Use this submission number to view or request deletion of this response.</span>
                        <div className="flex justify-between rounded-[8px] bg-black-100/50 px-4 py-2">
                            <span className="p4-new text-black-700">{responderId}</span>
                            <Copy
                                className="h-4 w-4 cursor-pointer text-brand-500"
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
        </>
    );
}
