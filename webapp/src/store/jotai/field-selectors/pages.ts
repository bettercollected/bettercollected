'use client';

import { v4 } from 'uuid';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { NodePosition } from '@app/models/types/form-builder-shared';
import { pruneOrphanedPipes } from '@app/utils/answer-piping';
import { pruneOrphanedConditions } from '@app/utils/conditional-logic';
import { pruneOrphanedDateRules, remapDateRules } from '@app/utils/date-rules';
import { fieldAndChildIds, movePageInSlides, pruneOutOfOrderReferences } from '@app/utils/form-outline';
import { SECTION_TITLE_MAX } from '@app/utils/leaflet-sections';
import { remapGroupChildIds, remapTextTokens } from '@app/utils/repeating-groups';

import type { BuilderContext } from './index';

/** Page mutations of the builder: add, duplicate, delete and move pages, and page settings (layout, image, theme, numbering, section title, flow position). */
export function pageMutators(ctx: BuilderContext) {
    const { formFields, setFormFields, activeSlideComponent, setActiveSlideComponent, activeSlide, getActiveSlide, reselectAfterMove } = ctx;

    const addSlide = (field: StandardFormFieldDto, index: number) => {
        formFields.splice(index, 0, field);
        formFields.map((slide, index: number) => {
            slide.index = index;
            return slide;
        });
        setFormFields([...formFields]);
    };

    const addSlideFormTemplate = (slide: StandardFormFieldDto, index?: number) => {
        const formSlide = {
            ...slide,
            id: v4()
        };
        let spliceIndex;
        if ((activeSlideComponent?.index || activeSlideComponent?.index === 0) && activeSlideComponent?.index >= 0) {
            spliceIndex = activeSlideComponent?.index + 1;
        } else {
            spliceIndex = formFields.length;
        }
        const updatedSlide = {
            ...formSlide,
            properties: {
                ...formSlide.properties,
                fields: [...(formSlide?.properties?.fields || [])].map((field) => ({
                    ...field,
                    id: v4()
                }))
            }
        };
        formFields.splice(spliceIndex, 0, { ...updatedSlide });

        const updatedFormFields = formFields.map((field, index) => ({
            ...field,
            index: index
        }));
        setFormFields([...updatedFormFields]);
        setActiveSlideComponent({ index: spliceIndex, id: formSlide.id });
        window.setTimeout(function () {
            const element = document.getElementById(formSlide.id);
            element?.scrollIntoView({
                behavior: 'smooth',
                block: 'end'
            });
        }, 500);
    };

    /**
     * Deep-copies a page and inserts it right after the source. Every field
     * gets a fresh id, and references that pointed WITHIN the page (logic
     * conditions, jump conditions, jump-to-self targets, piping chips) are
     * remapped to the new ids — otherwise the copy's rules would fire off the
     * original page's answers.
     */
    const duplicateSlide = (slideIndex: number) => {
        const source = formFields[slideIndex];
        if (!source) return;
        const clone: StandardFormFieldDto = JSON.parse(JSON.stringify(source));
        const oldSlideId = source.id;
        clone.id = v4();

        const idMap: Record<string, string> = {};
        clone.properties?.fields?.forEach((field) => {
            const newId = v4();
            idMap[field.id] = newId;
            field.id = newId;
            // Questions of a repeating group get fresh ids too.
            if (field.type === FieldTypes.GROUP && field.properties?.repeat) Object.assign(idMap, remapGroupChildIds(field));
        });

        const remapConditions = (conditions?: Array<{ fieldId: string; childFieldId?: string }>) => {
            conditions?.forEach((condition) => {
                if (condition && idMap[condition.fieldId]) condition.fieldId = idMap[condition.fieldId];
                if (condition?.childFieldId && idMap[condition.childFieldId]) condition.childFieldId = idMap[condition.childFieldId];
            });
        };
        clone.properties?.fields?.forEach((field) => {
            remapConditions(field.properties?.logic?.conditions);
            field.properties?.fields?.forEach((child) => field.type === FieldTypes.GROUP && remapConditions(child.properties?.logic?.conditions));
        });
        // Date rules between the page's questions follow them into the copy
        // (group siblings were remapped with their group).
        remapDateRules(clone.properties?.fields, idMap);
        clone.properties?.jumps?.forEach((jump) => {
            remapConditions(jump.conditions);
            if (jump.target === oldSlideId) jump.target = clone.id;
        });

        const remapPipes = (node: any): void => {
            if (node?.type === 'answerPipe' && node.attrs && idMap[node.attrs.pipeKey]) node.attrs.pipeKey = idMap[node.attrs.pipeKey];
            // Group pipes (`<groupId>:<aggregate>:<fieldId>`) remap per segment.
            if (node?.type === 'answerPipe' && node.attrs?.kind === 'group')
                node.attrs.pipeKey = String(node.attrs.pipeKey ?? '')
                    .split(':')
                    .map((part: string) => idMap[part] ?? part)
                    .join(':');
            node?.content?.forEach(remapPipes);
        };
        clone.properties?.fields?.forEach((field) => {
            if (field.title && typeof field.title !== 'string') remapPipes(field.title);
            if (field.type === FieldTypes.GROUP && field.properties?.repeat?.itemTitle) field.properties.repeat.itemTitle = remapTextTokens(field.properties.repeat.itemTitle, idMap);
        });

        // The flow-canvas position belongs to the original node.
        if (clone.properties?.position) delete clone.properties.position;

        formFields.splice(slideIndex + 1, 0, clone);
        formFields.forEach((slide, index) => (slide.index = index));
        setFormFields([...formFields]);
        setActiveSlideComponent({ id: clone.id, index: slideIndex + 1 });
        return clone.id;
    };

    const deleteSlide = (slideIndex: number) => {
        formFields.splice(slideIndex, 1);
        const updatedFormFields = formFields?.map((slide: StandardFormFieldDto, index) => {
            slide.index = index;
            return slide;
        });
        // Deleting a page removes its questions too — sweep conditions and
        // piping chips that pointed at them.
        pruneOrphanedConditions(updatedFormFields);
        pruneOrphanedPipes(updatedFormFields);
        pruneOrphanedDateRules(updatedFormFields);
        if (activeSlideComponent?.index === formFields.length) {
            setActiveSlideComponent({
                id: 'welcome-page',
                index: -10
            });
        }
        const next = [...updatedFormFields];
        setFormFields(next);
        // The state after the delete: what the undo toast restores from.
        return next;
    };

    const addMedia = (slideIndex: number, imageUrl: string) => {
        formFields[slideIndex].imageUrl = imageUrl;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    // Question numbering for the whole form: the flag lives on every
    // question page (StandardFieldProperty.showQuestionNumbers).
    const setShowQuestionNumbersOnAllPages = (show: boolean) => {
        setFormFields(formFields.map((slide) => (slide.type && slide.type !== FieldTypes.SLIDE ? slide : { ...slide, properties: { ...(slide.properties || {}), showQuestionNumbers: show } })));
    };

    const updateShowQuestionNumbers = (slideIndex: number, show: boolean) => {
        formFields![slideIndex]!.properties = {
            ...(formFields[slideIndex].properties || {}),
            showQuestionNumbers: show
        };
        setFormFields([...formFields]);
    };

    // A page's own section title (Leaflet bar and contents list). Kept as
    // typed; '' clears it (sent as '' so the save clears the stored one).
    const updateSlideSectionTitle = (slideIndex: number, sectionTitle: string) => {
        if (!formFields?.[slideIndex]) return;
        formFields[slideIndex]!.properties = {
            ...(formFields[slideIndex]!.properties || {}),
            sectionTitle: sectionTitle.slice(0, SECTION_TITLE_MAX)
        };
        setFormFields([...formFields], `sectionTitle:${formFields[slideIndex]!.id}`);
    };

    const updateSlideTheme = (color: { title: string; primary: string; secondary: string; tertiary: string; accent: string }) => {
        formFields[activeSlide?.index || 0].properties!.theme = {
            title: color.title,
            primary: color.primary,
            secondary: color.secondary,
            tertiary: color.tertiary,
            accent: color.accent
        };
        setFormFields([...formFields]);
    };

    const updateSlideLayout = (layout: FormSlideLayout) => {
        formFields[activeSlide?.index || 0].properties!.layout = layout;
        setFormFields([...formFields]);
    };

    const updateSlideImage = (imageUrl: string) => {
        formFields[activeSlide?.index || 0].imageUrl = imageUrl;
        setFormFields([...formFields]);
    };

    // Flow-view canvas position for a slide (cosmetic). Undefined → auto-layout.
    const updateSlidePosition = (slideIndex: number, position: NodePosition | undefined) => {
        if (!formFields?.[slideIndex]) return;
        formFields[slideIndex]!.properties = {
            ...(formFields[slideIndex]!.properties || {}),
            position
        };
        setFormFields([...formFields]);
    };

    // Reset every slide to auto-layout (used by the Flow view's "Auto-arrange").
    const clearSlidePositions = () => {
        formFields.forEach((slide) => {
            if (slide?.properties?.position) delete slide.properties.position;
        });
        setFormFields([...formFields]);
    };

    const deleteActiveSlide = () => {
        const slideIndex = getActiveSlide()?.index;
        formFields.splice(slideIndex!, 1);

        formFields.forEach((field, index) => {
            field.index = index;
        });

        const newActiveSlideIndex = slideIndex! - 1;
        if (newActiveSlideIndex < 0) {
            setActiveSlideComponent({
                id: 'welcome-page',
                index: -10
            });
        } else {
            const newFormField = formFields[newActiveSlideIndex];
            setActiveSlideComponent({
                id: newFormField?.id ?? v4(),
                index: newFormField.index
            });
        }

        setFormFields([...formFields]);
    };

    const resetFields = () => {
        setFormFields([]);
    };

    /**
     * Move page `from` to position `to` (outline drag or menu). One undo
     * step. Logic the new order turned around (a rule now using a later
     * answer) is removed; `prunedReferences` says how much, `next` is the
     * state after the move (what an undo toast restores from).
     */
    const movePage = (from: number, to: number): { next: StandardFormFieldDto[]; prunedReferences: number } | null => {
        const page = formFields[from];
        if (!page || !movePageInSlides(formFields, from, to)) return null;
        const movedFieldIds = new Set((page.properties?.fields ?? []).flatMap(fieldAndChildIds));
        const prunedReferences = pruneOutOfOrderReferences(formFields, movedFieldIds, new Set([page.id]));
        const next = [...formFields];
        setFormFields(next);
        reselectAfterMove();
        return { next, prunedReferences };
    };

    return { addSlide, addSlideFormTemplate, duplicateSlide, deleteSlide, addMedia, setShowQuestionNumbersOnAllPages, updateShowQuestionNumbers, updateSlideSectionTitle, updateSlideTheme, updateSlideLayout, updateSlideImage, updateSlidePosition, clearSlidePositions, deleteActiveSlide, resetFields, movePage };
}
