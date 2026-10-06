import { useEffect, useRef, useState } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { usePublishV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { PublishProblem, getPublishProblems, problemsFromPublishError, splitPublishProblems } from '@app/utils/publish-checks';

/** Where a question sits in the builder: its page, and the page-level field holding it. */
function locate(slides: Array<StandardFormFieldDto> | undefined, fieldId: string) {
    for (const [slideIndex, slide] of (slides ?? []).entries()) {
        for (const [fieldIndex, field] of (slide?.properties?.fields ?? []).entries()) {
            if (field.id === fieldId || (field.properties?.fields ?? []).some((child) => child.id === fieldId)) {
                return { slide: { id: slide.id, index: slideIndex }, field: { id: field.id, index: fieldIndex } };
            }
        }
    }
    return null;
}

/**
 * `fields`: the builder's live pages. Checks run on them, and publishing
 * waits (briefly) for the autosave to store them, so what is checked is what
 * the server checks and publishes.
 */
const PublishButton = ({ refresh = false, fields }: { refresh?: boolean; fields?: Array<StandardFormFieldDto> }) => {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const router = useRouter();
    const pathname = usePathname();
    const authState = useAppSelector(selectAuth);
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const [problems, setProblems] = useState<PublishProblem[]>([]);
    const [waiting, setWaiting] = useState(false);
    const savedFieldsRef = useRef(standardForm?.fields);
    useEffect(() => {
        savedFieldsRef.current = standardForm?.fields;
    }, [standardForm?.fields]);
    const checksVersion = standardForm?.settings?.publishChecksVersion;
    const { blocking, recommended } = splitPublishProblems(problems, checksVersion);
    const blocks = (found: PublishProblem[]) => splitPublishProblems(found, checksVersion).blocking.length > 0;

    // The server checks the saved draft: give the autosave (debounced) a
    // moment to store the fix the creator just made.
    const waitForSave = async () => {
        for (let i = 0; i < 20 && blocks(getPublishProblems(savedFieldsRef.current)); i++) {
            await new Promise((resolve) => setTimeout(resolve, 250));
        }
    };

    const publish = async () => {
        setProblems([]);
        if (fields?.length) {
            setWaiting(true);
            await waitForSave();
            setWaiting(false);
        }
        const response: any = await publishV2Form({
            workspaceId: workspace.id,
            formId: standardForm.formId
        });

        if (response.data) {
            if (refresh && pathname) {
                router.push(pathname);
                toast({ description: 'Form Published' });
                return;
            }
            openDialogModal('FORM_PUBLISHED');
            return;
        }
        // The server checks the same rules on the saved draft.
        const refused = problemsFromPublishError(response.error);
        if (refused.length) setProblems(refused);
        else toast({ description: "Couldn't publish the form. Please try again.", variant: 'destructive' });
    };

    const publishForm = async () => {
        // Honest defaults first: the creator sees what to fix, and where.
        const found = getPublishProblems(fields?.length ? fields : standardForm?.fields);
        if (found.length) {
            setProblems(found);
            return;
        }
        await publish();
    };

    const showQuestion = (fieldId: string) => {
        const place = locate(fields?.length ? fields : standardForm?.fields, fieldId);
        if (!place) return;
        setActiveSlideComponent(place.slide);
        setActiveFieldComponent(place.field);
        setProblems([]);
    };

    return (
        <>
            <Button isLoading={isLoading || waiting} onClick={publishForm} className="!bg-[#2456CC] text-white hover:!bg-[#1E49AD]" data-umami-event={'Publish Button'} data-umami-event-email={authState.email}>
                Publish
            </Button>
            <PublishProblemsDialog
                blocking={blocking}
                recommended={recommended}
                onClose={() => setProblems([])}
                onPublishAnyway={publish}
                onShowQuestion={showQuestion}
                canShowQuestion={(fieldId) => !!locate(fields?.length ? fields : standardForm?.fields, fieldId)}
            />
        </>
    );
};

/**
 * "Before you publish": problems that stop publishing (fix them first), and
 * recommendations that don't (publish anyway is offered when there is
 * nothing blocking).
 */
export function PublishProblemsDialog({
    blocking,
    recommended,
    onClose,
    onPublishAnyway,
    onShowQuestion,
    canShowQuestion
}: {
    blocking: PublishProblem[];
    recommended: PublishProblem[];
    onClose: () => void;
    onPublishAnyway: () => void;
    onShowQuestion: (fieldId: string) => void;
    canShowQuestion: (fieldId: string) => boolean;
}) {
    const open = blocking.length + recommended.length > 0;
    const count = (n: number) => (n === 1 ? 'One thing' : `${n} things`);
    const list = (items: PublishProblem[], testId: string) => (
        <ul className="flex flex-col gap-2" data-testid={testId}>
            {items.map((problem) => (
                <li key={`${problem.code}-${problem.fieldId}`} className="flex flex-col gap-1.5 rounded-lg border border-black-200 p-3 text-sm">
                    <span className="text-black-800">{problem.message}</span>
                    {canShowQuestion(problem.fieldId) && (
                        <button type="button" onClick={() => onShowQuestion(problem.fieldId)} className="w-fit text-xs font-semibold text-brand-600 underline underline-offset-2 hover:text-brand-700">
                            Show the question
                        </button>
                    )}
                </li>
            ))}
        </ul>
    );
    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
            <DialogContent className="max-w-lg" title="Before you publish">
                <DialogHeader>
                    <div aria-hidden="true" className="text-lg font-semibold leading-none tracking-tight">
                        Before you publish
                    </div>
                    <DialogDescription>
                        {blocking.length > 0
                            ? `${count(blocking.length)} would mislead or stop the people filling in this form. Fix ${blocking.length === 1 ? 'it' : 'them'} and publish again.`
                            : 'Recommended: people trust a form more when it says why it asks for their details. You can publish now and add this later.'}
                    </DialogDescription>
                </DialogHeader>
                <div className="flex max-h-[50vh] flex-col gap-3 overflow-y-auto">
                    {blocking.length > 0 && list(blocking, 'publish-problems')}
                    {recommended.length > 0 && (
                        <>
                            {blocking.length > 0 && <div className="text-xs font-semibold uppercase tracking-wide text-black-600">Also recommended</div>}
                            {list(recommended, 'publish-recommendations')}
                        </>
                    )}
                </div>
                {blocking.length === 0 && (
                    <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={onClose}>
                            Not now
                        </Button>
                        <Button onClick={onPublishAnyway} className="!bg-[#2456CC] text-white hover:!bg-[#1E49AD]">
                            Publish anyway
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

export default PublishButton;
