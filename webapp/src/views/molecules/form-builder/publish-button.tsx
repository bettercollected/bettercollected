import { useState } from 'react';

import { usePathname, useRouter } from 'next/navigation';

import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';
import { useTranslation } from 'react-i18next';

import { useShowNeedsReviewBanner } from '@app/components/open-formulieren-import/needs-review';
import { PublishBlockedByReviewDialog } from '@app/components/open-formulieren-import/publish-blocked-dialog';
import { useImportText } from '@app/components/open-formulieren-import/report-items';
import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';
import { usePropertiesTab } from '@app/store/jotai/properties-tab';
import { usePublishV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { PublishProblem, THEME_PROBLEM_ID, getPublishProblems, needsReviewProblem, problemsFromPublishError, splitPublishProblems, themeContrastProblems, workspaceTitleProblems } from '@app/utils/publish-checks';
import { flushAutosave } from '@app/views/molecules/form-builder/audo-save-form';

/** Where a question sits in the builder: its page, and the page-level field holding it. */
function locate(slides: Array<StandardFormFieldDto> | undefined, fieldId: string) {
    for (const [slideIndex, slide] of (slides ?? []).entries()) {
        // a page (a problem with one of its jumps)
        if (slide.id === fieldId) return { slide: { id: slide.id, index: slideIndex }, field: null };
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
 * first stores them (flushAutosave), so what is checked is what the server
 * checks and publishes.
 */
const PublishButton = ({
    refresh = false,
    fields: givenFields,
    getFields
}: {
    refresh?: boolean;
    fields?: Array<StandardFormFieldDto>;
    /** The live pages, read when the checks run (instead of `fields`). */ getFields?: () => Array<StandardFormFieldDto>;
}) => {
    const { toast } = useToast();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    // Only a workspace admin or owner can set the title (the workspace PATCH needs workspace.manage).
    const { can } = useWorkspacePermissions();
    const { openBottomSheetModal } = useBottomSheetModal();
    const [publishV2Form, { isLoading }] = usePublishV2FormMutation();
    const router = useRouter();
    const pathname = usePathname();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { setPropertiesTab } = usePropertiesTab();
    const [problems, setProblems] = useState<PublishProblem[]>([]);
    const { formState } = useFormState();
    const [waiting, setWaiting] = useState(false);
    const checksVersion = standardForm?.settings?.publishChecksVersion;
    // An import that still needs review is not published: the form's own mark (as the builder banner reads it)
    // tells before the click, and the server's `needs_review` problem when a stale mark let the click through.
    const importText = useImportText();
    const heldForReview = useShowNeedsReviewBanner(standardForm?.settings, workspace?.id);
    const [reviewDialog, setReviewDialog] = useState<{ importId: string; othersFollow: boolean } | null>(null);
    const { blocking, recommended } = splitPublishProblems(problems, checksVersion);

    const publish = async () => {
        setProblems([]);
        // The server publishes the saved draft: save every pending edit now
        // and wait for it, so an older draft is never published.
        setWaiting(true);
        const saved = await flushAutosave();
        setWaiting(false);
        if (saved === 'conflict') {
            toast({ description: 'This form was changed somewhere else. Reload the latest version before publishing.', variant: 'destructive' });
            return;
        }
        if (saved !== 'saved') {
            toast({ description: "Your latest changes aren't saved yet, so the form was not published. Check your connection and try again.", variant: 'destructive' });
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
        const unreviewed = needsReviewProblem(refused);
        // never silent: without an import id the dialog still explains (it just has no report to link to)
        if (unreviewed) setReviewDialog({ importId: unreviewed.importId || standardForm?.settings?.importId || '', othersFollow: refused.length > 1 });
        else if (refused.length) setProblems(refused);
        else toast({ description: "Couldn't publish the form. Please try again.", variant: 'destructive' });
    };

    const publishForm = async () => {
        if (heldForReview && standardForm?.settings?.importId) {
            setReviewDialog({ importId: standardForm.settings.importId, othersFollow: false });
            return;
        }
        const fields = getFields?.() ?? givenFields;
        // Honest defaults first: the creator sees what to fix, and where.
        // The builder's live endings with its live pages; the saved ones otherwise.
        const found = [
            // The workspace's title: who respondents see receiving their answers. It belongs to no question.
            ...workspaceTitleProblems(workspace, checksVersion),
            ...(fields?.length ? getPublishProblems(fields, formState.thankyouPage ?? null) : getPublishProblems(standardForm?.fields, standardForm?.thankyouPage ?? null)),
            // The builder's live theme with its live pages; the saved one otherwise.
            ...themeContrastProblems(fields?.length ? formState?.theme : standardForm?.theme)
        ];
        if (found.length) {
            setProblems(found);
            return;
        }
        await publish();
    };

    const shownFields = () => {
        const fields = getFields?.() ?? givenFields;
        return fields?.length ? fields : standardForm?.fields;
    };

    // The Design tab, where the contrast guard offers the fix. The inspector
    // shows its tabs only with a page selected, so select one if none is.
    const showTheme = () => {
        if (!activeSlideComponent?.id) {
            const first = shownFields()?.[0];
            if (first?.id) setActiveSlideComponent({ id: first.id, index: 0 });
        }
        setActiveFieldComponent(null);
        setPropertiesTab('design');
        setProblems([]);
    };

    // The workspace settings open over the builder, so nothing here is left: set the title, then publish again.
    const setWorkspaceTitle = () => {
        setProblems([]);
        openBottomSheetModal('WORKSPACE_SETTINGS', { initialIndex: 0 });
    };

    const showQuestion = (fieldId: string) => {
        if (fieldId === THEME_PROBLEM_ID) return showTheme();
        const place = locate(shownFields(), fieldId);
        if (!place) return;
        setActiveSlideComponent(place.slide);
        setActiveFieldComponent(place.field);
        setProblems([]);
    };

    return (
        <>
            <Button isLoading={isLoading || waiting} onClick={publishForm} className="text-white" data-umami-event={'Publish Button'} title={heldForReview ? importText('PUBLISH_BLOCKED.BUTTON_HINT') : undefined}>
                Publish
            </Button>
            <PublishBlockedByReviewDialog
                open={!!reviewDialog}
                importId={reviewDialog?.importId ?? ''}
                workspaceId={workspace?.id}
                workspaceName={workspace?.workspaceName}
                othersFollow={reviewDialog?.othersFollow ?? false}
                onClose={() => setReviewDialog(null)}
                onPublish={publishForm}
            />
            <PublishProblemsDialog
                blocking={blocking}
                recommended={recommended}
                onClose={() => setProblems([])}
                onPublishAnyway={publish}
                onShowQuestion={showQuestion}
                canShowQuestion={(fieldId) => fieldId === THEME_PROBLEM_ID || !!locate(shownFields(), fieldId)}
                canSetWorkspaceTitle={can(WorkspacePermission.WORKSPACE_MANAGE)}
                onSetWorkspaceTitle={setWorkspaceTitle}
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
    canShowQuestion,
    canSetWorkspaceTitle = false,
    onSetWorkspaceTitle
}: {
    blocking: PublishProblem[];
    recommended: PublishProblem[];
    onClose: () => void;
    onPublishAnyway: () => void;
    onShowQuestion: (fieldId: string) => void;
    canShowQuestion: (fieldId: string) => boolean;
    /** May the user set the workspace's title (workspace admins and owners)? Others are told to ask one. */
    canSetWorkspaceTitle?: boolean;
    /** Opens where the workspace's title is set; offered only with `canSetWorkspaceTitle`. */
    onSetWorkspaceTitle?: () => void;
}) {
    const { t } = useTranslation('builder');
    const open = blocking.length + recommended.length > 0;
    const count = (n: number) => (n === 1 ? 'One thing' : `${n} things`);
    const list = (items: PublishProblem[], testId: string) => (
        <ul className="flex flex-col gap-2" data-testid={testId}>
            {items.map((problem) => (
                <li key={`${problem.code}-${problem.fieldId}`} className="flex flex-col gap-1.5 rounded-lg border border-black-300 p-3 text-sm">
                    {/* the workspace's problem is worded here (translated, and by who the reader is), not by the server's sentence */}
                    <span className="text-black-800">{problem.code === 'workspace_title_missing' ? t(canSetWorkspaceTitle ? 'PUBLISH_WORKSPACE_TITLE.TEXT_MANAGE' : 'PUBLISH_WORKSPACE_TITLE.TEXT_MEMBER') : problem.message}</span>
                    {problem.code === 'workspace_title_missing' && canSetWorkspaceTitle && onSetWorkspaceTitle && (
                        <button type="button" onClick={onSetWorkspaceTitle} className="w-fit text-xs font-semibold text-brand-600 underline underline-offset-2 hover:text-brand-700">
                            {t('PUBLISH_WORKSPACE_TITLE.ACTION')}
                        </button>
                    )}
                    {problem.code !== 'workspace_title_missing' && canShowQuestion(problem.fieldId) && (
                        <button type="button" onClick={() => onShowQuestion(problem.fieldId)} className="w-fit text-xs font-semibold text-brand-600 underline underline-offset-2 hover:text-brand-700">
                            {problem.code === 'missing_ending' ? 'Show the page' : problem.code === 'theme_contrast' ? 'Show the theme' : 'Show the question'}
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
                    <div aria-hidden="true" className="text-lg leading-none font-semibold tracking-tight">
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
                            {blocking.length > 0 && <div className="text-xs font-semibold tracking-wide text-black-600 uppercase">Also recommended</div>}
                            {list(recommended, 'publish-recommendations')}
                        </>
                    )}
                </div>
                {blocking.length === 0 && (
                    <div className="flex justify-end gap-2">
                        <Button variant="secondary" onClick={onClose}>
                            Not now
                        </Button>
                        <Button onClick={onPublishAnyway} className="text-white">
                            Publish anyway
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

export default PublishButton;
