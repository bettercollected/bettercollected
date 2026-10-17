'use client';

import { FieldConditionalLogic, PageJump } from '@app/models/types/form-builder-shared';

import type { BuilderContext } from './index';

/** Logic mutations of the builder: show/hide rules on questions and page jumps. */
export function logicMutators(ctx: BuilderContext) {
    const { formFields, setFormFields } = ctx;

    // Conditional-visibility rule for a field (show/hide based on earlier answers).
    // Passing `undefined` clears the rule. Persists via `properties.logic`.
    const updateFieldConditionalLogic = (fieldIndex: number, slideIndex: number, logic: FieldConditionalLogic | undefined) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties || {}),
            logic
        };
        // Typing a condition's value is one undo step.
        setFormFields([...formFields], `logic:${formFields![slideIndex]!.properties!.fields![fieldIndex].id}`);
    };

    // Page-jump / branching rules for a slide. Persists via slide `properties.jumps`.
    const updateSlideJumps = (slideIndex: number, jumps: PageJump[] | undefined) => {
        formFields![slideIndex]!.properties = {
            ...(formFields![slideIndex]!.properties || {}),
            jumps
        };
        // Typing a jump's value is one undo step.
        setFormFields([...formFields], `jumps:${formFields![slideIndex]!.id}`);
    };

    return { updateFieldConditionalLogic, updateSlideJumps };
}
