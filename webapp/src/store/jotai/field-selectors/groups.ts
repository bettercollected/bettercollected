'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { RepeatSettings } from '@app/models/types/form-builder-shared';
import { pruneOrphanedPipes } from '@app/utils/answer-piping';
import { pruneOrphanedConditions } from '@app/utils/conditional-logic';
import { pruneOrphanedDateRules } from '@app/utils/date-rules';

import type { BuilderContext } from './index';

/** Repeating group mutations of the builder: the group's questions and its item settings. */
export function groupMutators(ctx: BuilderContext) {
    const { formFields, setFormFields } = ctx;

    // Repeating groups: the group's questions are edited as one list (add,
    // edit, reorder, remove). Removing a question sweeps rules/pipes that
    // referenced it, like deleting a page question does.
    const findField = (slideIndex: number, fieldId: string) => formFields?.[slideIndex]?.properties?.fields?.find((f) => f.id === fieldId);

    const updateGroupChildren = (slideIndex: number, groupId: string, children: StandardFormFieldDto[]) => {
        const group = findField(slideIndex, groupId);
        if (!group) return;
        const previousIds = (group.properties?.fields ?? []).map((child) => child.id);
        group.properties = { ...(group.properties || {}), fields: children.map((child, index) => ({ ...child, index })) };
        if (previousIds.some((id) => !children.some((child) => child.id === id))) {
            pruneOrphanedConditions(formFields);
            pruneOrphanedPipes(formFields);
        }
        // A question whose type changed is no longer a date its siblings can use.
        pruneOrphanedDateRules(formFields);
        setFormFields([...formFields]);
    };

    // Item limits, item label/title and export layout of a repeating group.
    const updateGroupRepeat = (slideIndex: number, groupId: string, repeat: RepeatSettings) => {
        const group = findField(slideIndex, groupId);
        if (!group) return;
        group.properties = { ...(group.properties || {}), repeat: { ...(group.properties?.repeat || {}), ...repeat } };
        setFormFields([...formFields]);
    };

    return { updateGroupChildren, updateGroupRepeat };
}
