'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { useStore } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@app/shadcn/components/ui/dialog';
import { selectForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useAutosaveStatus } from '@app/store/jotai/autosave-status';
import { useBuilderHydration } from '@app/store/jotai/builder-hydration';
import { IFormState, formStateAtom } from '@app/store/jotai/form';
import { builderFieldsAtom } from '@app/store/jotai/form-document';
import { usePatchV2FormMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { FlushResult, SaveOutcome, SaveQueue } from '@app/utils/autosave-queue';

/** Quiet time after the last edit before it is saved. */
export const AUTOSAVE_DEBOUNCE_MS = 1000;

/** How the server's answer to a save maps onto the queue. */
export function saveOutcomeOf(response: any): SaveOutcome {
    if (response?.data) return { kind: 'saved', version: response.data.updatedAt ?? null };
    const status = response?.error?.status;
    if (status === 409) return { kind: 'conflict' };
    if (status === 'FETCH_ERROR' || status === 'TIMEOUT_ERROR' || status === 502 || status === 503 || status === 504) return { kind: 'retryable' };
    return { kind: 'failed' };
}

// The open editor's queue, for the publish button and the AI panel (siblings
// in the tree).
let activeAutosave: { formId: string; flush: () => Promise<FlushResult>; adoptVersion: (version: string | null | undefined) => void } | null = null;

/**
 * The editor stored a newer version itself (an AI edit is saved by the
 * server): later saves build on it instead of reading it as a change made
 * elsewhere. Only for versions whose content the editor now shows.
 */
export function adoptAutosaveVersion(version: string | null | undefined) {
    activeAutosave?.adoptVersion(version);
}

/**
 * Save everything edited so far right away (skipping the debounce) and wait
 * for it. Resolves 'saved' when no editor is open.
 */
export async function flushAutosave(timeoutMs = 20000): Promise<FlushResult | 'timeout'> {
    if (!activeAutosave) return 'saved';
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<'timeout'>((resolve) => {
        timer = setTimeout(() => resolve('timeout'), timeoutMs);
    });
    try {
        return await Promise.race([activeAutosave.flush(), timeout]);
    } finally {
        clearTimeout(timer);
    }
}

/** What autosave reads: the form-level state and the builder's pages. */
interface SavedParts {
    formState: IFormState;
    fields: StandardFormFieldDto[];
}

const currentParts = (store: ReturnType<typeof useStore>): SavedParts => ({ formState: store.get(formStateAtom), fields: store.get(builderFieldsAtom) });
const sameParts = (a: SavedParts, b: SavedParts) => a.formState === b.formState && a.fields === b.fields;

/** What autosave sends: the form-level state with the builder's pages. */
function savedFormOf(formState: IFormState, fields: StandardFormFieldDto[]) {
    return {
        ...formState,
        welcomePage: {
            ...formState.welcomePage,
            title: formState.title
        },
        fields
    };
}

export default function AutoSaveForm({ formId }: { formId: string }) {
    // Autosave follows the form through store subscriptions, not renders:
    // typing does not re-render it.
    const store = useStore();
    const workspace = useAppSelector(selectWorkspace);
    const { hydratedFormId } = useBuilderHydration();
    const hydrated = hydratedFormId === formId;

    const dispatch = useAppDispatch();
    const form = useAppSelector(selectForm);
    const [patchV2Form] = usePatchV2FormMutation();
    const { setAutosaveStatus } = useAutosaveStatus();
    const [conflict, setConflict] = useState(false);

    // What the save request needs, kept current for the queue's sender.
    const contextRef = useRef({ workspaceId: workspace?.id as string | undefined, settings: form?.settings, patchV2Form, dispatch });
    useEffect(() => {
        contextRef.current = { workspaceId: workspace?.id, settings: form?.settings, patchV2Form, dispatch };
    });

    const [queue] = useState(
        () =>
            new SaveQueue(
                {
                    send: async (body, version) => {
                        const { workspaceId, patchV2Form: patch } = contextRef.current;
                        const formData = new FormData();
                        formData.append('form_body', body);
                        // The server refuses (409) a save based on an older draft.
                        if (version) formData.append('expected_updated_at', version);
                        const response: any = await patch({ formId, workspaceId, body: formData });
                        const outcome = saveOutcomeOf(response);
                        if (outcome.kind === 'saved') contextRef.current.dispatch(setForm({ ...response.data, settings: contextRef.current.settings }));
                        return outcome;
                    },
                    onState: (state, { savedAt }) => {
                        setAutosaveStatus(state === 'saved' ? { state, savedAt } : { state });
                        if (state === 'conflict') setConflict(true);
                    }
                },
                form?.updatedAt ?? null
            )
    );

    const latestRef = useRef(savedFormOf(store.get(formStateAtom), store.get(builderFieldsAtom)));
    const baselineTakenRef = useRef(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const allowLeaveRef = useRef(false);

    const enqueueLatest = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = null;
        if (!baselineTakenRef.current || !contextRef.current.workspaceId) return;
        queue.enqueue(JSON.stringify(latestRef.current));
    };

    // The form as it is now: the first state once hydrated is what the
    // server has; each later change is saved AUTOSAVE_DEBOUNCE_MS after the
    // last one.
    const takeState = (parts: SavedParts) => {
        const combinedFormState = savedFormOf(parts.formState, parts.fields);
        latestRef.current = combinedFormState;
        if (!hydratedRef.current) return;
        // The first state after loading is what the server has.
        if (!baselineTakenRef.current) {
            baselineTakenRef.current = true;
            queue.setBaseline(JSON.stringify(combinedFormState));
            return;
        }
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(enqueueLatest, AUTOSAVE_DEBOUNCE_MS);
    };
    const takeStateRef = useRef(takeState);
    const hydratedRef = useRef(hydrated);
    useLayoutEffect(() => {
        takeStateRef.current = takeState;
        hydratedRef.current = hydrated;
    });
    // What this render saw: hydrating takes it, as the render that hydrated showed it.
    const rendered: SavedParts = currentParts(store);

    useEffect(() => {
        takeState(rendered);
        // Changed since that render (by another mount effect): that is an edit.
        const now = currentParts(store);
        if (baselineTakenRef.current && !sameParts(now, rendered)) takeState(now);
    }, [hydrated]);

    useEffect(() => {
        // Each change of the pages or the form-level state, without re-rendering.
        let last = currentParts(store);
        const changed = () => {
            const now = currentParts(store);
            if (sameParts(now, last)) return;
            last = now;
            // Before hydrating (and taking the server's state) a change only updates what is latest.
            if (!baselineTakenRef.current) latestRef.current = savedFormOf(now.formState, now.fields);
            else takeStateRef.current(now);
        };
        const unsubscribe = [store.sub(builderFieldsAtom, changed), store.sub(formStateAtom, changed)];
        return () => unsubscribe.forEach((stop) => stop());
    }, [store]);

    // An edit made while the workspace was still loading saves once it is.
    useEffect(() => {
        if (workspace?.id && baselineTakenRef.current && !timerRef.current) enqueueLatest();
    }, [workspace?.id]);

    const hasUnsaved = () => {
        if (!baselineTakenRef.current) return false;
        return timerRef.current !== null || queue.hasUnsaved() || JSON.stringify(latestRef.current) !== queue.knownBody();
    };

    useEffect(() => {
        setAutosaveStatus({ state: 'idle' });
        activeAutosave = {
            formId,
            flush: () => {
                enqueueLatest();
                return queue.flush();
            },
            adoptVersion: (version) => queue.adoptVersion(version)
        };
        const onBeforeUnload = (event: BeforeUnloadEvent) => {
            if (allowLeaveRef.current || !hasUnsaved()) return;
            event.preventDefault();
            // Older browsers show the prompt only with returnValue set.
            event.returnValue = '';
        };
        const onOnline = () => queue.retryNow();
        window.addEventListener('beforeunload', onBeforeUnload);
        window.addEventListener('online', onOnline);
        return () => {
            window.removeEventListener('beforeunload', onBeforeUnload);
            window.removeEventListener('online', onOnline);
            if (activeAutosave?.formId === formId) activeAutosave = null;
            // Leaving the editor inside the app: save what the debounce held.
            if (timerRef.current) enqueueLatest();
        };
    }, [formId]);

    const reloadLatest = () => {
        allowLeaveRef.current = true;
        window.location.reload();
    };

    return (
        <Dialog open={conflict} onOpenChange={(open) => !open && setConflict(false)}>
            <DialogContent className="max-w-md" title="This form changed elsewhere">
                <DialogHeader>
                    <div aria-hidden="true" className="text-lg font-semibold leading-none tracking-tight">
                        This form changed elsewhere
                    </div>
                    <DialogDescription>
                        Someone saved this form in another tab or window after you opened it. Your latest changes here were not saved, so theirs are not overwritten. Reload to continue from the latest version.
                    </DialogDescription>
                </DialogHeader>
                <div className="flex justify-end gap-2">
                    <Button variant="secondary" onClick={() => setConflict(false)}>
                        Not now
                    </Button>
                    <Button onClick={reloadLatest} className="text-white" data-testid="reload-latest">
                        Reload latest
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
