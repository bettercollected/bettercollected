'use client';

import { JSONContent } from '@tiptap/react';
import { v4 } from 'uuid';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import { pruneOrphanedPipes } from '@app/utils/answer-piping';
import { reorder } from '@app/utils/array-utils';
import { pruneOrphanedCalculationRefs } from '@app/utils/calculated-fields';
import { pruneOrphanedConditions } from '@app/utils/conditional-logic';
import { pruneOrphanedDateRules } from '@app/utils/date-rules';
import { fieldAndChildIds, locateField, moveFieldInSlides, pruneOutOfOrderReferences } from '@app/utils/form-outline';
import { newRepeatingGroup, remapGroupChildIds } from '@app/utils/repeating-groups';

import type { BuilderContext } from './index';

/** Question mutations of the builder: add, insert, edit, move, duplicate and delete questions, and their settings. */
export function fieldMutators(ctx: BuilderContext) {
    const { formFields, setFormFields, activeFieldComponent, setActiveFieldComponent, activeSlide, activeField, reselectAfterMove } = ctx;

    const addField = (slideField: StandardFormFieldDto, slideIndex: number) => {
        const slide = formFields[slideIndex];
        slide?.properties?.fields!.push(slideField);
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateTitle = (fieldIndex: number, slideIndex: number, titleText: JSONContent) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex] = {
            ...(slide.properties!.fields![fieldIndex] || {}),
            title: titleText
        };
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides, `title:${slide.properties!.fields![fieldIndex].id}`);
    };

    const updateFieldImage = (imageUrl: string) => {
        formFields[activeSlide?.index || 0]!.properties!.fields![activeField?.index || 0]!.imageUrl = imageUrl;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateDescription = (fieldIndex: number, slideIndex: number, description: string | undefined) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex].description = description;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides, `description:${slide.properties!.fields![fieldIndex].id}`);
    };

    const updateFieldColSpan = (fieldIndex: number, slideIndex: number, colSpan: number) => {
        const existingSlide = formFields[slideIndex];
        const slide = { ...existingSlide };
        slide.properties!.fields![fieldIndex]['properties'] = { ...(slide.properties!.fields![fieldIndex].properties || { fields: [] }) };
        slide.properties!.fields![fieldIndex]!.properties!.colSpan = Math.min(12, Math.max(1, colSpan));
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldPlaceholder = (fieldIndex: number, slideIndex: number, placeholderText: string) => {
        const existingSlide = formFields[slideIndex];
        // The same text again (an input reporting its value on mount) is no edit.
        if ((existingSlide?.properties?.fields?.[fieldIndex]?.properties?.placeholder ?? '') === (placeholderText ?? '')) return;
        const slide = { ...existingSlide };
        slide.properties!.fields![fieldIndex]['properties'] = { ...(slide.properties!.fields![fieldIndex].properties || { fields: [] }) };
        slide.properties!.fields![fieldIndex]!.properties!.placeholder = placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides, `placeholder:${slide.properties!.fields![fieldIndex].id}`);
    };

    const updateFieldRequired = (fieldIndex: number, slideIndex: number, required: boolean) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            required: required
        };
        setFormFields([...formFields]);
    };

    // Internal ("for office use only"): hidden from respondents, filled in by
    // staff on each submission. Respondents never answer such a field, so any
    // logic or piping that read it is swept (the backend refuses it too).
    const updateFieldInternal = (fieldIndex: number, slideIndex: number, internal: boolean) => {
        const target = formFields[slideIndex].properties!.fields![fieldIndex];
        if (internal) target.internal = true;
        else delete target.internal;
        if (internal) {
            // Its own show/hide rule is moot too: staff always see it.
            if (target.properties?.logic) delete target.properties.logic;
            pruneOrphanedConditions(formFields);
            pruneOrphanedPipes(formFields);
            pruneOrphanedDateRules(formFields);
            pruneOrphanedCalculationRefs(formFields);
        }
        setFormFields([...formFields]);
    };

    const updateFieldValidation = (fieldIndex: number, slideIndex: number, validation: any) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            ...validation
        };
        setFormFields([...formFields]);
    };

    // Answer rules (validations beyond Required): merge `patch` into the
    // field's validations; undefined, null, NaN or '' removes a rule. Typing
    // into the same rule is one undo step.
    const updateFieldValidations = (fieldIndex: number, slideIndex: number, patch: Partial<IFormFieldValidation>) => {
        const target = formFields?.[slideIndex]?.properties?.fields?.[fieldIndex];
        if (!target) return;
        const next: Record<string, unknown> = { ...(target.validations || {}) };
        Object.entries(patch).forEach(([key, value]) => {
            if (value === undefined || value === null || value === '' || (typeof value === 'number' && !Number.isFinite(value))) delete next[key];
            else next[key] = value;
        });
        target.validations = next as IFormFieldValidation;
        setFormFields([...formFields], `validations:${target.id}:${Object.keys(patch).sort().join(',')}`);
    };

    const moveFieldInASlide = (slideIndex: number, sourceIndex: number, destinationIndex: number) => {
        if (destinationIndex < 0 || (activeSlide?.properties?.fields?.length || -1) < destinationIndex) return;
        formFields![slideIndex]!.properties!.fields = reorder(formFields![slideIndex]!.properties!.fields!, sourceIndex, destinationIndex);
        setFormFields([...formFields]);
        setTimeout(() => {
            setActiveFieldComponent({ index: destinationIndex, id: activeFieldComponent!.id });
        }, 0);
    };

    const updateFieldProperty = (fieldIndex: number, slideIndex: number, property: string, value: any) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties || {}),
            [property]: value
        };
        // Typing into one property (a formula, a label) is one undo step.
        setFormFields([...formFields], `property:${formFields![slideIndex]!.properties!.fields![fieldIndex].id}:${property}`);
    };

    // Duplicate a question in place. The clone gets a fresh id and lands right
    // after its source; piping chips / logic inside the clone keep pointing at
    // the fields they already referenced, which stay valid.
    const duplicateField = (slideIndex: number, fieldIndex: number) => {
        const source = formFields?.[slideIndex]?.properties?.fields?.[fieldIndex];
        if (!source) return;
        const clone = JSON.parse(JSON.stringify(source));
        clone.id = v4();
        // A duplicated repeating group gets its own questions; rules and
        // pipes between siblings follow them into the copy.
        if (clone.type === FieldTypes.GROUP && clone.properties?.repeat) remapGroupChildIds(clone);
        formFields[slideIndex]!.properties!.fields!.splice(fieldIndex + 1, 0, clone);
        formFields[slideIndex]!.properties!.fields = formFields[slideIndex]!.properties!.fields!.map((field, index) => ({
            ...field,
            index
        }));
        setFormFields([...formFields]);
        setActiveFieldComponent({ id: clone.id, index: fieldIndex + 1 });
    };

    const deleteField = (slideIndex: number, fieldIndex: number) => {
        formFields![slideIndex]!.properties!.fields!.splice(fieldIndex, 1);
        formFields![slideIndex!].properties!.fields = formFields![slideIndex!].properties!.fields?.map((field, index) => ({
            ...field,
            index
        }));
        // Sweep any logic or piping chips that referenced the removed question.
        pruneOrphanedConditions(formFields);
        pruneOrphanedPipes(formFields);
        pruneOrphanedDateRules(formFields);
        pruneOrphanedCalculationRefs(formFields);
        const next = [...formFields];
        setFormFields(next);
        setTimeout(() => {
            setActiveFieldComponent(null);
        }, 0);
        // The state after the delete: what the undo toast restores from.
        return next;
    };

    const updateRatingSteps = (slideIndex: number, fieldIndex: number, steps: number, type?: FieldTypes) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].type = type;
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties || {}),
            steps: steps
        };
        setFormFields([...formFields]);
    };

    const getNewField = (field: { name: string; type: FieldTypes; icon: any }, fieldId: string, slideIndex: number) => {
        const fieldIndex = formFields[slideIndex]?.properties?.fields?.length ? formFields[slideIndex]?.properties?.fields?.length! : 0;
        if (field.type === FieldTypes.YES_NO || field.type === FieldTypes.DROP_DOWN || field.type === FieldTypes.MULTIPLE_CHOICE) {
            const firstChoiceId = v4();
            const secondChoiceId = v4();
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    fields: [],
                    choices: [
                        {
                            id: firstChoiceId,
                            value: field.type === FieldTypes.YES_NO ? 'Yes' : ''
                        },
                        {
                            id: secondChoiceId,
                            value: field.type === FieldTypes.YES_NO ? 'No' : ''
                        }
                    ]
                }
            };
        } else if (field.type === FieldTypes.RATING || field.type === FieldTypes.LINEAR_RATING) {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    fields: [],
                    steps: field.type === FieldTypes.RATING ? 5 : 10
                }
            };
        } else if (field.type === FieldTypes.MATRIX) {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    fields: [
                        {
                            id: v4(),
                            title: '',
                            index: 0,
                            type: FieldTypes.MULTIPLE_CHOICE,
                            properties: {
                                choices: [
                                    {
                                        id: v4(),
                                        value: ''
                                    },
                                    {
                                        id: v4(),
                                        value: ''
                                    }
                                ]
                            }
                        },
                        {
                            id: v4(),
                            title: '',
                            index: 1,
                            type: FieldTypes.MULTIPLE_CHOICE,
                            properties: {
                                choices: [
                                    {
                                        id: v4(),
                                        value: ''
                                    },
                                    {
                                        id: v4(),
                                        value: ''
                                    }
                                ]
                            }
                        }
                    ]
                }
            };
        } else if (field.type === FieldTypes.GROUP) {
            return newRepeatingGroup(fieldId, fieldIndex);
        } else if (field.type === FieldTypes.TABULAR_INPUT) {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type,
                properties: {
                    rowTitles: ['Row 1', 'Row 2', 'Row 3'],
                    columnTitles: ['Col 1', 'Col 2', 'Col 3'],
                    tabular_value: [
                        ['', '', ''],
                        ['', '', ''],
                        ['', '', '']
                    ]
                }
            };
        } else {
            return {
                id: fieldId,
                index: fieldIndex,
                type: field.type
            };
        }
    };

    /**
     * Move a page-level question to page `toPageIndex`, position `toIndex`
     * (counted without the question), within its page or to another one.
     * Same contract as `movePage`.
     */
    const moveFieldToPage = (fieldId: string, toPageIndex: number, toIndex: number): { next: StandardFormFieldDto[]; prunedReferences: number } | null => {
        const at = locateField(formFields, fieldId);
        const field = at ? formFields[at.pageIndex].properties!.fields![at.fieldIndex] : undefined;
        if (!field || !moveFieldInSlides(formFields, fieldId, toPageIndex, toIndex)) return null;
        const prunedReferences = pruneOutOfOrderReferences(formFields, new Set(fieldAndChildIds(field)));
        const next = [...formFields];
        setFormFields(next);
        reselectAfterMove();
        return { next, prunedReferences };
    };

    // Insert a field at a position on a page (the canvas "+" and "/" menu).
    // With `replaceFieldId` the new field takes that field's place instead
    // (an empty text block someone typed "/" in), in one undo step.
    const addFieldAt = (slideField: StandardFormFieldDto, slideIndex: number, fieldIndex: number, replaceFieldId?: string) => {
        const slide = formFields[slideIndex];
        if (!slide) return;
        const fields = [...(slide.properties?.fields ?? [])];
        const replaceAt = replaceFieldId ? fields.findIndex((field) => field.id === replaceFieldId) : -1;
        if (replaceAt >= 0) fields.splice(replaceAt, 1, slideField);
        else fields.splice(Math.min(Math.max(fieldIndex, 0), fields.length), 0, slideField);
        slide.properties = { ...(slide.properties || {}), fields: fields.map((field, index) => ({ ...field, index })) };
        if (replaceAt >= 0) {
            pruneOrphanedConditions(formFields);
            pruneOrphanedPipes(formFields);
            pruneOrphanedDateRules(formFields);
            pruneOrphanedCalculationRefs(formFields);
        }
        setFormFields([...formFields]);
    };

    // The picture or video an image/video content block shows.
    const updateFieldAttachment = (slideIndex: number, fieldIndex: number, attachment: StandardFormFieldDto['attachment']) => {
        const field = formFields?.[slideIndex]?.properties?.fields?.[fieldIndex];
        if (!field) return;
        formFields[slideIndex]!.properties!.fields![fieldIndex] = { ...field, attachment };
        setFormFields([...formFields], `attachment:${field.id}`);
    };

    return { addField, updateTitle, updateFieldImage, updateDescription, updateFieldColSpan, updateFieldPlaceholder, updateFieldRequired, updateFieldInternal, updateFieldValidation, updateFieldValidations, moveFieldInASlide, updateFieldProperty, duplicateField, deleteField, updateRatingSteps, getNewField, moveFieldToPage, addFieldAt, updateFieldAttachment };
}
