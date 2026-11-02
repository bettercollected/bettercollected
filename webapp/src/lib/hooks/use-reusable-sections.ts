'use client';

import i18n from 'i18next';
import { useStore } from 'jotai';

import { applyOps } from '@app/lib/form-ops';
import type { FormOp } from '@app/lib/form-ops';
import type { LayoutContainer, StandardFormFieldDto } from '@app/models/dtos/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { dispatchAtom, formDocAtom } from '@app/store/jotai/form-document';
import { InsertTarget } from '@app/store/jotai/insert-target';
import { useCreateSectionMutation, useInstantiateSectionMutation, usePlanSectionUpdateMutation, useSaveSectionContentMutation } from '@app/store/reusable-sections/api';
import type { SectionDetail, SectionPlan } from '@app/store/reusable-sections/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { pageFieldsOf } from '@app/utils/layout-containers';
import { instanceContainers, instanceFields, libraryOf, refusalText, replaceTarget, spliceOps } from '@app/utils/reusable-sections';

/**
 * What the builder does with the workspace's library of reusable sections. Inserting and updating a copy are
 * one `splice_fields` op each (one undo step) through the ops engine, so the engine's checks decide what is
 * accepted and the server checks every save as usual. Reads the document when an edit is made.
 */
export function useSectionActions() {
    const store = useStore();
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId = workspace?.id as string;
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const [instantiate] = useInstantiateSectionMutation();
    const [createSection] = useCreateSectionMutation();
    const [saveContent] = useSaveSectionContentMutation();
    const [planUpdate] = usePlanSectionUpdateMutation();

    const doc = () => store.get(formDocAtom);
    const send = (ops: unknown[], label: string): string | null => {
        if (store.set(dispatchAtom, { ops: ops as any, label })) return null;
        // refused: say why, as the engine's own result does
        const refused = applyOps(doc() as any, ops as FormOp[], { atomic: true }).results.find((result) => !result.ok);
        return refused?.message ?? i18n.t('builder:SECTIONS_LIB.TOAST.NOT_INSERTED');
    };
    const fail = (message: string) => toast({ variant: 'destructive', description: message });

    /** Where an insert goes: the canvas target, else the end of the selected page. */
    const placeFor = (target: InsertTarget | null | undefined, activeSlide: { id: string; index: number } | null) => {
        const pages = doc().fields ?? [];
        const page = target ? pages[target.slideIndex] : activeSlide && activeSlide.index >= 0 ? pages[activeSlide.index] : undefined;
        if (!page) return null;
        return { page, slideIndex: target ? target.slideIndex : (activeSlide as { index: number }).index, index: target ? target.fieldIndex : undefined };
    };

    return {
        /** Copy a library section into a page (`target`: the canvas position, else the end of the selected page). */
        async insert(sectionId: string, target: InsertTarget | null | undefined, activeSlide: { id: string; index: number } | null): Promise<boolean> {
            const place = placeFor(target, activeSlide);
            if (!place) {
                toast({ description: i18n.t('builder:TOASTS.ADD_PAGE_FIRST') });
                return false;
            }
            const result: any = await instantiate({ workspaceId, sectionId });
            if (!result.data) {
                fail(refusalText(result.error, i18n.t('builder:SECTIONS_LIB.TOAST.NOT_INSERTED')));
                return false;
            }
            const fragment = result.data;
            const refusal = send(spliceOps(place.page.id, fragment, { index: place.index }), 'Insert section');
            if (refusal) {
                fail(refusal);
                return false;
            }
            const first = fragment.fields[0]?.id as string | undefined;
            if (first) {
                const fields = pageFieldsOf(doc().fields?.[place.slideIndex] as any);
                setActiveSlideComponent({ id: place.page.id, index: place.slideIndex });
                setActiveFieldComponent({
                    id: first,
                    index: Math.max(
                        0,
                        fields.findIndex((field) => field.id === first)
                    )
                });
            }
            toast({ description: i18n.t('builder:SECTIONS_LIB.TOAST.INSERTED', { count: fragment.fields.length }) });
            return true;
        },

        /** Save questions of a page (and a container that holds them) as a new library section. */
        async saveAsSection(args: { pageId: string; fieldIds: string[]; containerId?: string; name: string; description?: string }): Promise<SectionDetail | null> {
            const page = (doc().fields ?? []).find((p) => p?.id === args.pageId);
            const wanted = new Set(args.fieldIds);
            const fields = pageFieldsOf(page as any).filter((field) => wanted.has(field.id));
            const containers = ((page?.properties?.containers ?? []) as LayoutContainer[]).filter((container) => container.id === args.containerId);
            const result: any = await createSection({ workspaceId, name: args.name, description: args.description || undefined, fields, containers });
            if (!result.data) {
                fail(refusalText(result.error, i18n.t('builder:SECTIONS_LIB.TOAST.NOT_SAVED')));
                return null;
            }
            return result.data as SectionDetail;
        },

        /** The questions of the copy `instance` on the page, and its containers, as a save to the library sends them. */
        copyOf(pageId: string, instance: string): { fields: StandardFormFieldDto[]; containers: LayoutContainer[] } {
            const page = (doc().fields ?? []).find((p) => p?.id === pageId);
            const fields = instanceFields(page as any, instance);
            return { fields, containers: instanceContainers(page as any, new Set(fields.map((field) => field.id))) };
        },

        /** A copy of the section's newest version: what it would do to this copy (the diff). */
        async planUpdate(pageId: string, instance: string): Promise<SectionPlan | null> {
            const { fields } = this.copyOf(pageId, instance);
            const sectionId = libraryOf(fields[0])?.sectionId;
            if (!sectionId) return null;
            const result: any = await planUpdate({ workspaceId, sectionId, instance, fields });
            if (!result.data) {
                fail(refusalText(result.error, i18n.t('builder:SECTIONS_LIB.TOAST.NOT_UPDATED')));
                return null;
            }
            return result.data as SectionPlan;
        },

        /** Replace the copy by the plan's fragment, where it is (one undo step). */
        applyUpdate(pageId: string, plan: SectionPlan): boolean {
            const page = (doc().fields ?? []).find((p) => p?.id === pageId);
            const target = replaceTarget(page as any, plan.instance);
            if (!target) return false;
            const refusal = send(spliceOps(pageId, plan, target), 'Update from library');
            if (refusal) {
                fail(refusal);
                return false;
            }
            toast({ description: i18n.t('builder:SECTIONS_LIB.TOAST.UPDATED') });
            return true;
        },

        /** Save the copy as the section's next version (the copy's questions keep their place in the section). */
        async saveCopy(pageId: string, instance: string): Promise<SectionDetail | null> {
            const { fields, containers } = this.copyOf(pageId, instance);
            const origin = libraryOf(fields[0]);
            if (!origin) return null;
            const result: any = await saveContent({ workspaceId, sectionId: origin.sectionId, fields, containers, expectedVersion: origin.version });
            if (!result.data) {
                fail(result.error?.data?.code === 'section_changed' ? i18n.t('builder:SECTIONS_LIB.TOAST.NEWER_VERSION') : refusalText(result.error, i18n.t('builder:SECTIONS_LIB.TOAST.NOT_SAVED')));
                return null;
            }
            // the copy now matches this version: its markers say so (the creator's own changes stay)
            const bumped = fields.map((field) => ({ op: 'replace_field', field: { ...field, properties: { ...field.properties, library: { ...libraryOf(field), version: (result.data as SectionDetail).version } } } }));
            send(bumped, 'Save copy to library');
            return result.data as SectionDetail;
        }
    };
}
