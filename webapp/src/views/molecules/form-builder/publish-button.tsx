import { useState } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { usePublishV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { PublishProblem, getPublishProblems, problemsFromPublishError } from '@app/utils/publish-checks';

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

const PublishButton = ({ refresh = false }: { refresh?: boolean }) => {
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

    const publishForm = async () => {
        // Honest defaults first: the creator sees what to fix, and where.
        const found = getPublishProblems(standardForm?.fields);
        if (found.length) {
            setProblems(found);
            return;
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

    const showQuestion = (fieldId: string) => {
        const place = locate(standardForm?.fields, fieldId);
        if (!place) return;
        setActiveSlideComponent(place.slide);
        setActiveFieldComponent(place.field);
        setProblems([]);
    };

    return (
        <>
            <Button isLoading={isLoading} onClick={publishForm} className="!bg-[#2456CC] text-white hover:!bg-[#1E49AD]" data-umami-event={'Publish Button'} data-umami-event-email={authState.email}>
                Publish
            </Button>
            <Dialog open={problems.length > 0} onOpenChange={(open) => !open && setProblems([])}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Before you publish</DialogTitle>
                        <DialogDescription>
                            {problems.length === 1 ? 'One thing' : `${problems.length} things`} would mislead or stop the people filling in this form. Fix {problems.length === 1 ? 'it' : 'them'} and publish again.
                        </DialogDescription>
                    </DialogHeader>
                    <ul className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto" data-testid="publish-problems">
                        {problems.map((problem) => (
                            <li key={`${problem.code}-${problem.fieldId}`} className="flex flex-col gap-1.5 rounded-lg border border-black-200 p-3 text-sm">
                                <span className="text-black-800">{problem.message}</span>
                                {locate(standardForm?.fields, problem.fieldId) && (
                                    <button type="button" onClick={() => showQuestion(problem.fieldId)} className="w-fit text-xs font-semibold text-brand-600 underline underline-offset-2 hover:text-brand-700">
                                        Show the question
                                    </button>
                                )}
                            </li>
                        ))}
                    </ul>
                </DialogContent>
            </Dialog>
        </>
    );
};

export default PublishButton;
