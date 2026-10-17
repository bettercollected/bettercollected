import React, { FormEvent, useState } from 'react';

import { useRouter } from 'next-nprogress-bar';
import Image from 'next/image';

import { ChevronDown } from 'lucide-react';
import styled from 'styled-components';

import { AIOptIn, useWorkspaceAI } from '@app/components/ai/ai-consent';
import OutlineReview from '@app/components/ai/outline-review';
import { Button } from '@app/shadcn/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@app/shadcn/components/ui/collapsible';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useBuildFormFromOutlineMutation, useOutlineFormWithAIMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { FormOutline, outlineForBuild, outlineProblems, questionCount } from '@app/utils/ai-outline';

const GradiantBorderDiv = styled.div`
    position: relative;
    padding: 1px;

    &::before {
        border-radius: 7px;
        content: '';
        opacity: 0;
        z-index: -1;
        inset: 0;
        position: absolute;
        background: var(--color-brand-500);
        transition: opacity 0.25s linear;
    }

    &:hover::before {
        opacity: 1;
    }
`;

const examples = ["Contact form to gather user’s information. Include fields for the user's name, email address, and phone number among others.", 'A form to collect suggestions for improving the design and functionality of an marketing app.'];

type Step = 'prompt' | 'outlining' | 'review' | 'building';

/** The message of an API error ({code, message} or plain text), if any. */
function errorMessage(error: any, fallback: string): string {
    const data = error?.data;
    if (data && typeof data === 'object' && typeof data.message === 'string') return data.message;
    if (typeof data === 'string' && data.length < 300) return data;
    return fallback;
}

function Waiting({ title, detail }: { title: string; detail: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-10" role="status" aria-live="polite">
            <div>
                <Image width={60} height={60} style={{ objectFit: 'cover' }} className="rounded-image" src="/gifs/loading.gif" alt="" />
            </div>
            <div className="mt-10 font-semibold">{title}</div>
            <div className="mt-2 text-xs text-black-700">{detail}</div>
        </div>
    );
}

export default function StartWithAi() {
    const { toast } = useToast();
    const [prompt, setPrompt] = React.useState('');
    const [isOpen, setIsOpen] = React.useState(false);
    const workspace = useAppSelector(selectWorkspace);
    const [requestOutline] = useOutlineFormWithAIMutation();
    const [buildForm] = useBuildFormFromOutlineMutation();
    const [step, setStep] = useState<Step>('prompt');
    const [outline, setOutline] = useState<FormOutline | null>(null);
    // Workspace AI opt-in (#715)
    const { settings: aiSettings, enabled: aiEnabled, providerName } = useWorkspaceAI();

    const router = useRouter();

    // Step 1: the AI drafts an outline; nothing is created yet.
    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!aiEnabled || !prompt.trim()) return;
        setStep('outlining');
        const response: any = await requestOutline({ workspaceId: workspace.id, body: { prompt: prompt.trim() } });
        if (response.data?.outline) {
            setOutline(response.data.outline);
            setStep('review');
            return;
        }
        setStep('prompt');
        toast({ description: errorMessage(response.error, 'Could not draft an outline, please try again'), variant: 'destructive' });
    };

    // Step 2: the reviewed outline becomes a draft form.
    const handleBuild = async () => {
        if (!outline || outlineProblems(outline).length) return;
        setStep('building');
        const response: any = await buildForm({ workspaceId: workspace.id, body: { outline: outlineForBuild(outline) } });
        if (response.data?.formId) {
            const notes: string[] = response.data.notes ?? [];
            const findings = response.data.quality?.findings?.length ?? 0;
            if (notes.length || findings) {
                toast({ description: [...notes, findings ? `${findings} thing${findings === 1 ? '' : 's'} to check before publishing.` : ''].filter(Boolean).join(' ') });
            }
            router.replace(`/${workspace?.workspaceName}/dashboard/forms/${response.data.formId}/edit`);
            return;
        }
        setStep('review');
        toast({ description: errorMessage(response.error, 'Could not build the form, please try again'), variant: 'destructive' });
    };

    if (step === 'outlining') return <Waiting title="Drafting an outline" detail="You can review and change it before anything is created" />;
    if (step === 'building') return <Waiting title="Building your form" detail="Your draft opens in the editor when it is ready" />;

    if (step === 'review' && outline) {
        const problems = outlineProblems(outline);
        return (
            <div>
                <div className="p2-new border-b border-b-black-300 p-4">Start with AI</div>
                <div className="flex flex-col gap-4 px-10 py-6">
                    <div>
                        <div className="tex-black-800 text-normal font-medium">Review the outline</div>
                        <p className="mt-1 text-xs text-black-600">
                            {outline.pages.length} page{outline.pages.length === 1 ? '' : 's'}, {questionCount(outline)} question{questionCount(outline) === 1 ? '' : 's'}. Rename, reorder, delete or add questions, then build the form. Nothing is created
                            until you do.
                        </p>
                    </div>
                    <div>
                        <label htmlFor="outline-title" className="text-xs text-black-700">
                            Form title
                        </label>
                        <input id="outline-title" className="w-full rounded-md border border-black-300 px-2 py-1.5 text-sm" value={outline.title} maxLength={200} onChange={(event) => setOutline({ ...outline, title: event.target.value })} />
                    </div>
                    <div className="max-h-[55vh] overflow-y-auto pr-1">
                        <OutlineReview outline={outline} onChange={setOutline} />
                    </div>
                    {problems.length > 0 && (
                        <ul className="text-xs text-red-600" aria-live="polite">
                            {problems.map((problem) => (
                                <li key={problem}>{problem}</li>
                            ))}
                        </ul>
                    )}
                    <div className="flex justify-between gap-4">
                        <Button type="button" variant="v2Button" onClick={() => setStep('prompt')}>
                            Back to prompt
                        </Button>
                        <Button data-umami-event={'Building Form from AI outline'} type="button" onClick={handleBuild} disabled={problems.length > 0}>
                            <div className="z-10 flex items-center gap-2">
                                <AIIcon aria-hidden="true" />
                                Build form
                            </div>
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <form onSubmit={handleSubmit}>
            <div className="p2-new border-b border-b-black-300 p-4">Start with AI</div>
            <div className="flex flex-col gap-4 px-10 py-6">
                <div className="tex-black-800 text-normal font-medium">Create a new form with AI</div>
                {aiSettings && !aiEnabled && <AIOptIn feature="Start with AI" sends="your prompt, the workspace AI profile and your AI memory" />}
                <div className="prompt-input-wrapper rounded-lg bg-black-200 p-[1px]">
                    <div className="rounded-lg bg-white">
                        <label htmlFor="start-with-ai-prompt" className="sr-only">
                            Describe the form you need
                        </label>
                        <textarea
                            id="start-with-ai-prompt"
                            className="w-full rounded-lg border-none text-sm placeholder-black-500"
                            style={{
                                resize: 'none'
                            }}
                            rows={4}
                            value={prompt}
                            placeholder="E.g. Design a contact form with fields for name, email, subject, message, and field to upload media."
                            onChange={(event) => {
                                setPrompt(event.target.value);
                            }}
                        />
                    </div>
                </div>
                <div className="flex justify-between gap-4">
                    <div>
                        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
                            <CollapsibleTrigger asChild>
                                <div className="mb-2 flex cursor-pointer items-center gap-2 text-sm font-medium text-black-700">
                                    Examples <ChevronDown />
                                </div>
                            </CollapsibleTrigger>
                            <CollapsibleContent className={cn('flex flex-col gap-2 transition-all duration-300', isOpen ? 'h-auto' : 'h-0')}>
                                {examples.map((example: string) => {
                                    return (
                                        <GradiantBorderDiv
                                            key={example}
                                            onClick={() => {
                                                setPrompt(example);
                                                setIsOpen(false);
                                            }}
                                        >
                                            <div className="cursor-pointer rounded-lg bg-black-200 p-4 text-sm text-black-600 hover:text-black-800">{example}</div>
                                        </GradiantBorderDiv>
                                    );
                                })}
                            </CollapsibleContent>
                        </Collapsible>
                    </div>
                    <Button data-umami-event={'Creating Form with AI'} className="group" type="submit" disabled={!aiEnabled || !prompt.trim()}>
                        <div className="z-10 flex items-center gap-2">
                            <AIIcon aria-hidden="true" />
                            {outline ? 'Draft a new outline' : 'Draft outline'}
                        </div>
                    </Button>
                </div>
                {outline && (
                    <button type="button" className="self-start text-xs font-medium text-black-700 underline" onClick={() => setStep('review')}>
                        Back to the outline you were reviewing
                    </button>
                )}
                {aiEnabled && <p className="text-xs leading-relaxed text-black-600">Draft outline sends your prompt, the workspace AI profile and your AI memory to {providerName}. You review the outline before anything is created.</p>}
            </div>
        </form>
    );
}

const AIIcon = (props: React.SVGAttributes<any>) => {
    return (
        <svg width="24" height="25" viewBox="0 0 24 25" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M15.7739 10.7054C11.2572 9.77189 10.6405 9.10768 9.77367 4.24346C9.76144 4.17495 9.72743 4.11317 9.67748 4.06874C9.62754 4.02431 9.56478 4 9.5 4C9.43522 4 9.37246 4.02431 9.32251 4.06874C9.27257 4.11317 9.23855 4.17495 9.22632 4.24346C8.35971 9.10768 7.74298 9.77189 3.22606 10.7054C3.16245 10.7186 3.10508 10.7552 3.06382 10.809C3.02257 10.8628 3 10.9304 3 11.0001C3 11.0699 3.02257 11.1375 3.06382 11.1913C3.10508 11.2451 3.16245 11.2817 3.22606 11.2949C7.74298 12.2284 8.35971 12.8926 9.22632 17.7568C9.23861 17.8253 9.27265 17.887 9.32259 17.9313C9.37253 17.9757 9.43525 18 9.5 18C9.56474 18 9.62747 17.9757 9.67741 17.9313C9.72735 17.887 9.76138 17.8253 9.77367 17.7568C10.6405 12.8926 11.2572 12.2284 15.7739 11.2949C15.8376 11.2817 15.8949 11.2451 15.9362 11.1913C15.9774 11.1375 16 11.0699 16 11.0001C16 10.9304 15.9774 10.8628 15.9362 10.809C15.8949 10.7552 15.8376 10.7186 15.7739 10.7054Z"
                fill="white"
            />
            <path
                d="M20.8609 17.8317C18.0814 17.2982 17.7019 16.9187 17.1684 14.1391C17.1609 14.1 17.14 14.0647 17.1092 14.0393C17.0785 14.0139 17.0399 14 17 14C16.9601 14 16.9215 14.0139 16.8908 14.0393C16.86 14.0647 16.8391 14.1 16.8316 14.1391C16.2983 16.9187 15.9188 17.2982 13.1391 17.8317C13.1 17.8392 13.0647 17.8601 13.0393 17.8909C13.0139 17.9216 13 17.9602 13 18.0001C13 18.0399 13.0139 18.0786 13.0393 18.1093C13.0647 18.14 13.1 18.161 13.1391 18.1685C15.9188 18.7019 16.2983 19.0815 16.8316 21.861C16.8391 21.9001 16.8601 21.9354 16.8908 21.9608C16.9216 21.9861 16.9602 22 17 22C17.0398 22 17.0784 21.9861 17.1092 21.9608C17.1399 21.9354 17.1609 21.9001 17.1684 21.861C17.7019 19.0815 18.0814 18.7019 20.8609 18.1685C20.9 18.161 20.9353 18.14 20.9607 18.1093C20.9861 18.0786 21 18.0399 21 18.0001C21 17.9602 20.9861 17.9216 20.9607 17.8909C20.9353 17.8601 20.9 17.8392 20.8609 17.8317Z"
                fill="white"
            />
            <path
                d="M18.9304 7.91583C17.5407 7.64911 17.3509 7.45934 17.0842 6.06956C17.0804 6.04999 17.07 6.03233 17.0546 6.01964C17.0392 6.00694 17.0199 6 17 6C16.9801 6 16.9608 6.00694 16.9454 6.01964C16.93 6.03233 16.9196 6.04999 16.9158 6.06956C16.6491 7.45934 16.4594 7.64911 15.0696 7.91583C15.05 7.91959 15.0323 7.93006 15.0196 7.94543C15.0069 7.96079 15 7.9801 15 8.00004C15 8.01997 15.0069 8.03928 15.0196 8.05465C15.0323 8.07002 15.05 8.08048 15.0696 8.08425C16.4594 8.35097 16.6491 8.54074 16.9158 9.93051C16.9196 9.95007 16.93 9.96771 16.9454 9.98039C16.9608 9.99307 16.9801 10 17 10C17.0199 10 17.0392 9.99307 17.0546 9.98039C17.07 9.96771 17.0804 9.95007 17.0842 9.93051C17.3509 8.54074 17.5407 8.35097 18.9304 8.08425C18.95 8.08048 18.9677 8.07002 18.9804 8.05465C18.9931 8.03928 19 8.01997 19 8.00004C19 7.9801 18.9931 7.96079 18.9804 7.94543C18.9677 7.93006 18.95 7.91959 18.9304 7.91583Z"
                fill="white"
            />
        </svg>
    );
};
