import type { FieldRuleStates } from '@app/lib/field-rules';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { getInputFieldsById } from '@app/utils/answer-piping';
import { validateAnswerRulesInSlide } from '@app/utils/answer-rules';
import { LogicSources, getHiddenFieldIds, logicSourcesById } from '@app/utils/conditional-logic';
import { validateDateRulesInSlide } from '@app/utils/date-rules';
import { OptionStates } from '@app/utils/option-logic';
import { validateGroupsInSlide } from '@app/utils/repeating-groups';
import { validateSlide } from '@app/utils/vvalidation-utils';

/**
 * What stops the respondent from leaving a page with these answers: missing
 * required answers, repeating-group limits, answer rules (length, format,
 * range, number of options) and date rules. Keys are the ids the questions
 * render under (a question inside a group item: its item-scoped id), the
 * shape `setInvalidFields` and the question wrapper take. Only questions the
 * respondent can see count (logic-hidden ones are left out), and a question
 * the form fills in or locks is not theirs to correct.
 *
 * The one place the page's Continue and the review page read this, so a page
 * is "complete" by the same rule in both. `options`: the options the
 * questions offer (choice logic); without them every option counts as offered
 * and the server's check is the one that refuses a hidden one.
 */
export function pageInvalidations(page: StandardFormFieldDto | undefined, slides: StandardFormFieldDto[] | undefined, answers: Record<string, any>, ruleStates: FieldRuleStates, sources: LogicSources = logicSourcesById(slides), options?: OptionStates): Record<string, any> {
    const fields = page?.properties?.fields ?? [];
    const hidden = getHiddenFieldIds(fields, answers, sources);
    const visibleSlide = { ...page, properties: { ...page?.properties, fields: fields.filter((f: StandardFormFieldDto) => !hidden.has(f.id)) } } as StandardFormFieldDto;
    const visibleFields = (visibleSlide.properties?.fields ?? []) as StandardFormFieldDto[];
    const invalidations: Record<string, any> = {
        ...validateSlide(visibleSlide, answers, ruleStates, options),
        // Repeating groups: item limits, and required questions per item
        // (keyed by the item-scoped id the question renders under).
        ...validateGroupsInSlide(visibleFields, answers, sources, ruleStates)
    };
    // Answer rules on answers given; a missing one is Required's to report.
    // (A question the form sets or locks is not the respondent's to correct.)
    Object.entries(validateAnswerRulesInSlide(visibleFields, answers, sources, ruleStates.locked, options)).forEach(([id, problems]) => {
        if (!invalidations[id]) invalidations[id] = problems;
    });
    // Date rules (e.g. "after Start date"), on top of a missing answer.
    Object.entries(validateDateRulesInSlide(visibleFields, answers, getInputFieldsById(slides), undefined, ruleStates.locked)).forEach(([id, problems]) => {
        invalidations[id] = [...(invalidations[id] ?? []), ...problems];
    });
    return invalidations;
}
