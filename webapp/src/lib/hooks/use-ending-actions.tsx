'use client';

import { useStore } from 'jotai';

import { DELETE_UNDO_MS } from '@app/lib/hooks/use-undoable-delete';
import { FormSlideLayout } from '@app/models/enums/form';
import { JUMP_TARGET_SUBMIT, PageJump } from '@app/models/types/form-builder-shared';
import { ToastAction } from '@app/shadcn/components/ui/toast';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom, { initialFieldsAtom } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { ENDING_NAME_MAX_LENGTH, Ending, MAX_ENDINGS, defaultEndingIndex, endingLabel, jumpEndingId, jumpsFallBackToDefault, newEndingId, withEndingIds } from '@app/utils/endings';

/**
 * The builder's ending actions (outline menu, properties panel): add,
 * duplicate, rename, make default and delete. A form keeps at least one
 * ending. Deleting an ending that page jumps name makes those jumps show the
 * default ending (they still submit), and the toast's Undo brings the ending
 * and those jumps back.
 */
export function useEndingActions() {
    const { toast } = useToast();
    const { formState, setFormState } = useFormState();
    const { formFields, setFormFields } = useFormFieldsAtom();
    const { setActiveThankYouPageComponent } = useActiveThankYouPageComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    // The toast's Undo runs later: it reads the slides as they are then.
    const store = useStore();

    const endings: Ending[] = withEndingIds(formState.thankyouPage?.length ? formState.thankyouPage : [{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }]);

    const select = (index: number) => {
        setActiveThankYouPageComponent({ id: `ending-${index}`, index });
        setActiveSlideComponent({ id: 'thank-you-page', index: -20 });
    };

    const setEndings = (update: (current: Ending[]) => Ending[]) => {
        setFormState((prev) => ({ ...prev, thankyouPage: update(withEndingIds(prev.thankyouPage?.length ? prev.thankyouPage : [{ layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }])) }));
    };

    const canAdd = endings.length < MAX_ENDINGS;

    const addEnding = () => {
        const index = endings.length;
        if (!canAdd) return -1;
        setEndings((current) => [...current, { id: newEndingId(), layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND }]);
        select(index);
        return index;
    };

    const duplicateEnding = (index: number) => {
        const source = endings[index];
        if (!source || !canAdd) return;
        const name = source.name?.trim() ? `${source.name.trim()} (copy)`.slice(0, ENDING_NAME_MAX_LENGTH) : undefined;
        setEndings((current) => {
            const copy: Ending = { ...JSON.parse(JSON.stringify(current[index] ?? source)), id: newEndingId(), name, isDefault: undefined };
            return [...current.slice(0, index + 1), copy, ...current.slice(index + 1)];
        });
        select(index + 1);
    };

    const renameEnding = (index: number, name: string) => {
        const trimmed = name.slice(0, ENDING_NAME_MAX_LENGTH);
        setEndings((current) => current.map((ending, i) => (i === index ? { ...ending, name: trimmed.trim() ? trimmed : undefined } : ending)));
    };

    const makeDefault = (index: number) => {
        setEndings((current) => current.map((ending, i) => ({ ...ending, isDefault: i === index ? true : undefined })));
    };

    const deleteEnding = (index: number) => {
        if (endings.length <= 1) return;
        const removed = endings[index];
        if (!removed) return;
        const label = endingLabel(removed, index, endings.length);
        setEndings((current) => current.filter((ending) => ending.id !== removed.id));
        // Which jumps named it, so Undo can point them back.
        const repointed: Array<{ slideId: string; jumpIndex: number }> = [];
        (formFields ?? []).forEach((slide) =>
            ((slide.properties?.jumps as PageJump[] | undefined) ?? []).forEach((jump, jumpIndex) => {
                if (jumpEndingId(jump) === removed.id) repointed.push({ slideId: slide.id, jumpIndex });
            })
        );
        const fallback = removed.id ? jumpsFallBackToDefault(formFields ?? [], removed.id) : null;
        if (fallback) setFormFields(fallback.slides);
        // Stay on the endings: show the one respondents now see by default.
        const remaining = endings.filter((ending) => ending.id !== removed.id);
        select(Math.max(0, defaultEndingIndex(remaining)));

        const count = fallback?.count ?? 0;
        toast({
            description: count ? `${label} deleted. ${count} jump${count === 1 ? ' now shows' : 's now show'} the default ending.` : `${label} deleted`,
            duration: DELETE_UNDO_MS,
            action: (
                <ToastAction altText="Undo deleting the ending" onClick={() => undoDelete(removed, index, repointed)}>
                    Undo
                </ToastAction>
            )
        });
    };

    // Bring the ending back where it was and point its jumps at it again
    // (only jumps that still submit to the default ending).
    const undoDelete = (removed: Ending, index: number, repointed: Array<{ slideId: string; jumpIndex: number }>) => {
        setFormState((prev) => {
            const current = withEndingIds(prev.thankyouPage);
            if (current.some((ending) => ending.id === removed.id)) return prev;
            // Only one default: the restored one keeps it only if no other has it now.
            const restored = removed.isDefault && current.some((ending) => ending.isDefault) ? { ...removed, isDefault: undefined } : removed;
            const at = Math.min(index, current.length);
            return { ...prev, thankyouPage: [...current.slice(0, at), restored, ...current.slice(at)] };
        });
        if (repointed.length) {
            setFormFields(
                (store.get(initialFieldsAtom) ?? []).map((slide) => {
                    const mine = repointed.filter((entry) => entry.slideId === slide.id);
                    if (!mine.length) return slide;
                    const jumps = ((slide.properties?.jumps as PageJump[] | undefined) ?? []).map((jump, jumpIndex) =>
                        mine.some((entry) => entry.jumpIndex === jumpIndex) && jump.target === JUMP_TARGET_SUBMIT && !jump.endingId ? { ...jump, endingId: removed.id } : jump
                    );
                    return { ...slide, properties: { ...slide.properties, jumps } };
                })
            );
        }
        select(Math.min(index, endings.length - 1));
    };

    return { endings, canAdd, addEnding, duplicateEnding, renameEnding, makeDefault, deleteEnding };
}
