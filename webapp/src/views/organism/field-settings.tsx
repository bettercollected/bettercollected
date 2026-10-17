'use client';

import { ComponentProps, useId, useState } from 'react';

import { useAtomValue } from 'jotai';

import { formFieldsList } from '@app/constants/form-fields';
import globalConstants from '@app/constants/global';
import { jsonEqual } from '@app/lib/form-ops/model';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { activeFieldAtom, activeSlideAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderFieldsValue, useField, useFieldActions, usePageShell } from '@app/store/jotai/entity-hooks';
import useFormFieldsAtom, { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { answerRuleKind } from '@app/utils/answer-rules';
import { getDateRuleSources } from '@app/utils/date-rules';
import { canBeInternal } from '@app/utils/internal-fields';
import { WHY_WE_ASK_MAX_LENGTH, asksForIdentity } from '@app/utils/publish-checks';
import { isRepeatingGroup } from '@app/utils/repeating-groups';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import AnswerRulesSettings from '@app/views/molecules/form-builder/answer-rules-settings';
import CalculatedFieldSettings from '@app/views/molecules/form-builder/calculated-field-settings';
import DateFieldSettings from '@app/views/molecules/form-builder/date-field-settings';
import FieldConditionalLogicEditor from '@app/views/molecules/form-builder/field-conditional-logic';
import { InspectorSection, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';
import RepeatingGroupSettings from '@app/views/molecules/form-builder/repeating-group-settings';

// Field types that show content and collect no answer.
const DISPLAY_ONLY_FIELD_TYPES: Array<string | null | undefined> = [FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, FieldTypes.GROUP];

// Field types that take no field image.
const NON_IMAGE_FIELD_TYPES: Array<string | null | undefined> = [FieldTypes.TEXT, null, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT, FieldTypes.GROUP];

// 12-column grid: Full = 12, 1/2 = 6, … adjacent fields whose spans fit
// share a row on desktop; mobile always stacks.
const WIDTH_OPTIONS = [
    { label: 'Full', name: 'Full width', span: 12 },
    { label: '2/3', name: 'Two thirds', span: 8 },
    { label: '1/2', name: 'Half', span: 6 },
    { label: '1/3', name: 'One third', span: 4 },
    { label: '1/4', name: 'One quarter', span: 3 }
] as const;

// Settings components that draw their own top rule: inside a section the
// section's heading separates them already.
const NO_OWN_RULE = '[&>div]:border-t-0 [&>div]:pt-0';

/**
 * The selected question's settings in the inspector, in groups: Basics,
 * Answer rules, Privacy, Logic and Appearance. The breadcrumb above
 * (properties-drawer.tsx) leads back to the page and the form.
 */
export default function FieldSettings() {
    // The selected question and its page's own settings only: typing in
    // another question does not re-render the inspector.
    const activeFieldComponent = useAtomValue(activeFieldAtom);
    const activeSlideComponent = useAtomValue(activeSlideAtom);
    const activeField = useField(activeFieldComponent?.id);
    const activeSlide = usePageShell(activeSlideComponent?.id);
    const { updateFieldRequired, updateDescription, updateFieldProperty, updateFieldColSpan, updateFieldValidations } = useFieldActions();
    const { updateFieldInternal, updateRatingSteps, updateFieldImage, updateAllowMultipleSelectionMatrixField } = useBuilderActions();

    const [errorMsg, setErrorMsg] = useState('');
    const [stepValue, setStepValue] = useState(activeField?.properties?.steps);
    const baseId = useId();
    // Another question selected (or the steps changed elsewhere): show its steps.
    const [shownSteps, setShownSteps] = useState(activeField?.properties?.steps);
    if (shownSteps !== activeField?.properties?.steps) {
        setShownSteps(activeField?.properties?.steps);
        setStepValue(activeField?.properties?.steps);
    }

    // The selection can point past the page's questions (e.g. right after a
    // delete): every setting below writes to activeField, so show none (the
    // breadcrumb above still leads back).
    if (!activeField || !activeSlide) {
        return <p className="px-4 py-6 text-xs text-black-600">This question is no longer on the page.</p>;
    }

    const field = activeField;
    const slide = activeSlide;

    const handleStepsChange = (e: any) => {
        setErrorMsg('');
        if (e.target.value <= 0 || e.target.value >= 50) {
            setErrorMsg('Value cant be less than 1 or greater than 50.');
        } else {
            updateRatingSteps(slide.index, field.index, e.target.value, field.type);
        }
        setStepValue(e.target.value);
    };

    const typeName = formFieldsList.find((f) => f.type === field.type)?.name ?? field.type?.replaceAll('_', ' ').toLowerCase();
    const title = extractTextfromJSON(field);
    const isChoice = field.type === FieldTypes.MULTIPLE_CHOICE || field.type === FieldTypes.MATRIX;
    const isRating = field.type === FieldTypes.LINEAR_RATING || field.type === FieldTypes.RATING;
    // Content with nothing to answer can't be required (a dead end at
    // publish); the switch stays while it is on, so it can be turned off.
    const showRequired = field.type !== FieldTypes.TEXT && field.type !== FieldTypes.CALCULATED && !isRepeatingGroup(field) && (!DISPLAY_ONLY_FIELD_TYPES.includes(field.type) || !!field.validations?.required);
    const ruleKind = answerRuleKind(field);
    const showWhyWeAsk = !field.internal && (asksForIdentity(field) || !!field.properties?.whyWeAsk);
    const colSpan = Math.min(12, Math.max(1, field.properties?.colSpan ?? 12));
    const stepsId = `${baseId}-steps`;
    const widthId = `${baseId}-width`;

    return (
        <div className="flex flex-col">
            <div className="flex flex-col gap-1.5 px-4 pt-4">
                <div className="truncate text-sm font-semibold text-black-800" title={title}>
                    {title || 'Untitled question'}
                </div>
                {field.type && <span className="w-fit rounded bg-black-100 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-black-600 uppercase">{typeName}</span>}
            </div>

            <InspectorSection title="Basics">
                <SettingSwitch label="Description" checked={field.description !== undefined && field.description !== null} onCheckedChange={(checked) => updateDescription(field.id, checked ? '' : undefined)} />
                {showRequired && (
                    <SettingSwitch label={field.type === FieldTypes.MATRIX ? 'Require a response in each row' : 'Required'} checked={!!field.validations?.required} onCheckedChange={(checked) => updateFieldRequired(field.id, checked)} />
                )}
                {field.type === FieldTypes.MULTIPLE_CHOICE && <SettingSwitch label="“Other” option" checked={!!field.properties?.allowOtherChoice} onCheckedChange={(checked) => updateFieldProperty(field.id, 'allowOtherChoice', checked)} />}
                {isChoice && (
                    <SettingSwitch
                        label="Multiple selection"
                        checked={!!field.properties?.allowMultipleSelection}
                        onCheckedChange={(checked) => {
                            if (field.type === FieldTypes.MATRIX) updateAllowMultipleSelectionMatrixField(checked);
                            else updateFieldProperty(field.id, 'allowMultipleSelection', checked);
                        }}
                    />
                )}
                {isRating && (
                    <div className="flex flex-col gap-2">
                        <div className="flex flex-row items-center justify-between text-xs">
                            <label htmlFor={stepsId} className="text-black-700">
                                Steps
                            </label>
                            <input
                                id={stepsId}
                                type="number"
                                value={stepValue ?? ''}
                                onChange={(e) => handleStepsChange(e)}
                                aria-invalid={!!errorMsg || undefined}
                                aria-describedby={errorMsg ? `${stepsId}-error` : undefined}
                                className="h-8 w-14 rounded border border-control p-0 px-2 text-center text-sm focus:border-brand-500"
                            />
                        </div>
                        {errorMsg && (
                            <span id={`${stepsId}-error`} className="text-xs text-[#C43D3D]">
                                {errorMsg}
                            </span>
                        )}
                    </div>
                )}
                {isRepeatingGroup(field) && (
                    <div className={NO_OWN_RULE}>
                        <RepeatingGroupSettings field={field} slide={slide} />
                    </div>
                )}
            </InspectorSection>

            {field.type === FieldTypes.CALCULATED && (
                <InspectorSection title="Calculation">
                    <CalculationSettings field={field} onChange={(property, value) => updateFieldProperty(field.id, property, value)} />
                </InspectorSection>
            )}

            {(ruleKind || field.type === FieldTypes.DATE) && (
                <InspectorSection title="Answer rules">
                    {ruleKind && <AnswerRulesSettings field={field} onChange={(patch) => updateFieldValidations(field.id, patch)} />}
                    {field.type === FieldTypes.DATE && (
                        <DateRuleSettings field={field} onChange={(patch) => Object.entries(patch).forEach(([property, value]) => updateFieldProperty(field.id, property, value))} />
                    )}
                </InspectorSection>
            )}

            {(showWhyWeAsk || canBeInternal(field)) && (
                <InspectorSection title="Privacy">
                    {showWhyWeAsk && <WhyWeAskSetting value={field.properties?.whyWeAsk ?? ''} required={asksForIdentity(field)} onChange={(value) => updateFieldProperty(field.id, 'whyWeAsk', value)} />}
                    {canBeInternal(field) && (
                        <SettingSwitch
                            label="Internal (staff only)"
                            checked={!!field.internal}
                            onCheckedChange={(checked) => updateFieldInternal(field.index, slide.index, checked)}
                            hint={
                                field.internal
                                    ? 'Respondents never see this field. Your team fills it in on each response. Required applies to your team, not respondents.'
                                    : 'For office use only: hide this field from respondents and fill it in on each response.'
                            }
                        />
                    )}
                </InspectorSection>
            )}

            {!field.internal && (
                <InspectorSection title="Logic">
                    <div className={NO_OWN_RULE}>
                        <FieldConditionalLogicEditor />
                    </div>
                </InspectorSection>
            )}

            <InspectorSection title="Appearance">
                <div className="flex w-full flex-col gap-1.5">
                    <div id={widthId} className="text-xs text-black-700">
                        Width
                    </div>
                    <div className="flex overflow-hidden rounded-md border border-control" role="group" aria-labelledby={widthId}>
                        {WIDTH_OPTIONS.map((option) => {
                            const selected = colSpan === option.span;
                            return (
                                <button
                                    key={option.span}
                                    type="button"
                                    aria-pressed={selected}
                                    aria-label={option.name}
                                    onClick={() => updateFieldColSpan(field.id, option.span)}
                                    className={`flex-1 px-1 py-1.5 text-[11px] font-medium transition-colors ${selected ? 'bg-brand-100 text-brand-600' : 'bg-white text-black-600 hover:bg-black-100'}`}
                                >
                                    {option.label}
                                </button>
                            );
                        })}
                    </div>
                    <p className="text-[11px] leading-relaxed text-black-600">Fields that fit side by side share a row. Phones always stack.</p>
                </div>
                {!NON_IMAGE_FIELD_TYPES.includes(field.type) && <SettingSwitch label="Field image" checked={!!field.imageUrl} onCheckedChange={(checked) => updateFieldImage(checked ? field.imageUrl || globalConstants.defaultFieldImage : '')} />}
            </InspectorSection>
        </div>
    );
}

/**
 * A calculated question's settings: its variables, preview and problems
 * read every question, so this section follows the whole form.
 */
function CalculationSettings({ field, onChange }: { field: StandardFormFieldDto; onChange: (property: string, value: unknown) => void }) {
    const { formFields } = useFormFieldsAtom();
    const { formState } = useFormState();
    return <CalculatedFieldSettings field={field} slides={formFields || []} hiddenNames={formState.hiddenFields ?? []} endings={formState.thankyouPage ?? []} onChange={onChange} />;
}

/** A date question's rules: the earlier dates it may compare with, derived from the form. */
function DateRuleSettings({ field, onChange }: { field: StandardFormFieldDto; onChange: ComponentProps<typeof DateFieldSettings>['onChange'] }) {
    const fieldId = field.id;
    const sources = useBuilderFieldsValue((formFields) => getDateRuleSources(formFields || [], fieldId), [fieldId], jsonEqual);
    return <DateFieldSettings field={field} sources={sources} onChange={onChange} />;
}

/**
 * "Why we ask this" for a question that collects an email, a phone number or
 * an ID number: shown to respondents under the question, and needed before
 * the form can be published (utils/publish-checks.ts).
 */
export function WhyWeAskSetting({ value, required, onChange }: { value: string; required: boolean; onChange: (value: string) => void }) {
    const missing = required && !value.trim();
    return (
        <div className="flex w-full flex-col gap-1">
            <label htmlFor="why-we-ask" className="text-xs font-medium text-black-700">
                Why we ask this
            </label>
            <textarea
                id="why-we-ask"
                value={value}
                maxLength={WHY_WE_ASK_MAX_LENGTH}
                rows={2}
                placeholder="e.g. So we can send you a copy of your answers."
                aria-invalid={missing}
                aria-describedby="why-we-ask-help"
                onChange={(e) => onChange(e.target.value)}
                className={`w-full rounded-lg border p-2 text-xs ${missing ? 'border-amber-500' : 'border-control focus:border-brand-500'}`}
            />
            <span id="why-we-ask-help" className={`text-[11px] leading-relaxed ${missing ? 'text-amber-700' : 'text-black-600'}`}>
                {missing ? 'This question asks for personal details. Say briefly why you need them; the form can’t be published without it.' : 'Shown to respondents under the question.'}
            </span>
        </div>
    );
}
