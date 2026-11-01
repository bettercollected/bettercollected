import { KeyboardEvent, MouseEvent, useContext, useEffect, useMemo, useRef } from 'react';

import parse from 'html-react-parser';
import { AlertCircle } from 'lucide-react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useFormContentLanguage from '@app/lib/hooks/use-form-content-language';
import { useOptionStates } from '@app/lib/hooks/use-option-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useGroupItemScope } from '@app/store/jotai/group-item-scope';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { resolvePipesInText, resolvePipesInTitle, stringTitleToDoc } from '@app/utils/answer-piping';
import { hasAnyPart } from '@app/utils/address';
import { answerRuleMessage, browserChecksPattern, checkAnswerRules, isAnswerRuleProblem } from '@app/utils/answer-rules';
import { rawDateRange } from '@app/utils/date-range';
import { isAnswerableField } from '@app/utils/leaflet-sections';
import { legacyTitleText } from '@app/utils/legacy-title';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { isServerProblem, serverProblemMessage } from '@app/utils/server-answer-errors';
import { HEADING_CLASSES, TEXT_BLOCK_BODY_CLASSES } from '@app/utils/text-headings';
import { Invalidations } from '@app/utils/vvalidation-utils';
import { themed } from '@app/views/molecules/theme/theme-root';
import { contrast, invalidEdge, requiredMarkColour, softInk, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { RenderImage } from '@app/views/organism/form-builder/fields/render-field';

import { QuestionLabel, QuestionLabelContext } from './question-label-context';
import { QuestionNumberContext } from './question-number-context';

/**
 * A question as respondents see it: title, "optional" or required mark,
 * description, "why we ask this", the field's own controls (`children`) and
 * the validation message.
 *
 * The controls are named by the title and described by the rest through
 * QuestionLabelContext (useQuestionLabel), not by their placeholders. `group`
 * makes the whole question a labelled group, for fields made of several
 * controls with no group of their own (a matrix, a repeating group).
 */
export default function QuestionWrapper({ field, children, errorMessage, group = false }: { field: StandardFormFieldDto; children?: React.ReactNode; errorMessage?: string; group?: boolean }) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const tokens = styleTokens(theme?.style);
    const { hiddenValues } = useHiddenFieldValues();
    const standardForm = useAppSelector(selectForm);

    const { invalidFields } = formResponse;
    const { t, language } = useRespondentLanguage();
    // Field rules (lib/field-rules.ts): what the form's rules decide for this
    // question from the answers now. Inside a repeating-group item they are
    // decided per item. A form without rules gets NO_RULES, which changes nothing.
    const itemScope = useGroupItemScope();
    const ruleStates = useFieldRuleStates();
    const ruleText = ruleStates.text(field.id, itemScope?.groupId, itemScope?.index);
    // A question the form fills in or locks (a rule sets its value or makes it read-only).
    const locked = !itemScope && ruleStates.isLocked(field.id);
    // The author's text (title, description, reason) is marked when the form
    // declares another language than the page's; the chrome around it is not.
    const contentLang = useFormContentLanguage();
    // Answer rules (length, format, range, number of options): flagged on
    // Continue, then re-checked against the answer as it is now, so the
    // message goes away as soon as the answer is fixed.
    const isAnswerable = isAnswerableField(field);
    // Choice logic (utils/option-logic.ts): a question with nothing to choose is never required.
    const optionStates = useOptionStates();
    const nothingToChoose = !itemScope && optionStates.isNoneLeft(field.id);
    // Required unless a rule says otherwise (never for a locked question).
    const isRequired = !nothingToChoose && ruleStates.isRequired(field.id, !!field?.validations?.required, itemScope?.groupId, itemScope?.index);
    // The page's own "required" (the enum's 0) flagged earlier goes away when a rule
    // stops requiring the question. What the server said stays: it is the server's
    // word on the answer it was sent, and only the next Continue replaces it.
    const flagged = (invalidFields?.[field.id] ?? []).filter((code) => ruleStates.isEmpty || isRequired || code !== Invalidations.REQUIRED);
    // A date range with one end given is flagged "required" by the answer rules; it is re-checked like the other rules (and an empty one is only ever the page's "required").
    const rangeAnswer = rawDateRange(formResponse.answers?.[field.id]);
    // The same for an address with a part missing: "required" about an answer that is there is an answer rule's.
    const addressRule = field.type === FieldTypes.ADDRESS && flagged.includes('REQUIRED') && hasAnyPart(formResponse.answers?.[field.id]?.address);
    const rangeRule = (field.type === FieldTypes.DATE_RANGE && flagged.includes('REQUIRED') && !!(rangeAnswer?.start || rangeAnswer?.end)) || addressRule;
    const flaggedOnlyRules = flagged.length > 0 && flagged.every((code) => isAnswerRuleProblem(code) || (rangeRule && code === 'REQUIRED'));
    const ruleProblems = flaggedOnlyRules ? checkAnswerRules(field, formResponse.answers?.[field.id], optionStates) : [];
    // A custom pattern is not tested in the browser (utils/answer-rules.ts): only
    // the server finds a miss, and its message stays until the next Continue.
    const serverPattern = flagged.includes('PATTERN') && !!field?.validations?.regex && !browserChecksPattern(field.validations.regex);
    const ruleMessage = ruleProblems.length ? answerRuleMessage(field, ruleProblems[0], t, language) : serverPattern ? answerRuleMessage(field, 'PATTERN', t) : undefined;
    // Problems only the server finds (an answer of the wrong kind).
    const serverProblem = flagged.find(isServerProblem);
    const serverMessage = serverProblem ? serverProblemMessage(serverProblem, t) : undefined;
    // A caller may own the error (e.g. a repeating group's item-count message).
    const hasError = errorMessage !== undefined ? !!errorMessage : flaggedOnlyRules ? !!ruleMessage : flagged.length > 0;

    // A field that collects an answer is either required or optional — never
    // ambiguous. We mark required fields (asterisk) AND label optional ones, so
    // no one is nudged into answering something they could skip. Display-only
    // fields (statements, images) collect nothing, so they carry no marker.
    // (DESIGN.md §5: "Don't hide which fields are optional to coerce answers".)
    // A text block is content, not a question: it reads as body text (its
    // own headings keep their sizes), not in the question-label style.
    const isTextBlock = field?.type === FieldTypes.TEXT;
    // Fields with controls to name: the answerable ones, calculated values and
    // repeating groups. Text blocks, images and videos have none.
    const hasControls = !!field?.type && ![FieldTypes.TEXT, FieldTypes.IMAGE_CONTENT, FieldTypes.VIDEO_CONTENT].includes(field.type);

    // Answer piping: swap pipe tokens for the responder's earlier answers (or
    // captured hidden-field values) before the title/description hit the DOM.
    const pipeContext = { slides: standardForm?.fields, answers: formResponse.answers ?? {}, hiddenValues, language };
    // Plain-string titles (groups, AI/MCP-created fields) go through the TipTap
    // path as text nodes — never as raw HTML — so neither the title nor a piped
    // answer or URL prefill can inject markup. Bold keeps the string path's look.
    // An untitled field shows no title: never the builder's placeholder hint.
    const legacy = field ? legacyTitleText(field) : undefined;
    // A rule's title replaces the question's (plain text, same pipe tokens).
    const stringTitle = ruleText?.title ? ruleText.title : typeof field?.title === 'string' && field.title ? field.title : legacy;
    const title = stringTitle ? stringTitleToDoc(stringTitle, [{ type: 'bold' }]) : field?.title;
    const resolvedTitle = resolvePipesInTitle(title, pipeContext);
    const titleHtml = getHtmlFromJson(resolvedTitle) ?? '';
    const resolvedDescription = resolvePipesInText(ruleText?.description ?? field?.description, pipeContext);
    // "Why we ask this": the creator's reason for an identifying question.
    const whyWeAsk = field?.properties?.whyWeAsk?.trim();
    // Leaflet: the question's n.m number, set in the margin column.
    const numbering = useContext(QuestionNumberContext);
    const number = numbering?.numbers[field.id];
    const leaflet = tokens.key === 'leaflet';
    // Numerals wear the action colour where it reads as text on the page, else the ink.
    const numberColour = theme?.secondary && theme?.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme?.primary;

    // While the error shows, the field's own controls say so too: they are
    // marked invalid and described by the message, and their edge turns
    // signal red. The main control gets this through useQuestionLabel; this
    // also reaches the secondary ones (an "Other" answer, table cells,
    // matrix rows) without threading it through every component.
    const groupRef = useRef<HTMLDivElement>(null);
    const errorId = `q-error-${field.id}`;
    const titleId = `q-title-${field.id}`;
    const requiredId = `q-required-${field.id}`;
    const lockedId = `q-locked-${field.id}`;

    // The name the field's controls carry: the title as rendered (rich text
    // and piped answers included) and, inside a repeating-group item, that
    // item's heading ("Child 2"). An untitled question names nothing here, so
    // a control falls back to its own label.
    // Any visible character outside a tag means there is a title to name by.
    const hasTitle = /(^|>)[^<]*\S/.test(titleHtml);
    const itemHeadingId = itemScope ? `group-item-${itemScope.groupId}-${itemScope.index}` : undefined;
    const labelledBy = [hasTitle ? titleId : null, itemHeadingId].filter(Boolean).join(' ') || undefined;
    // Described in reading order: description, "why we ask", then the error.
    const infoIds = [resolvedDescription ? `q-desc-${field.id}` : null, whyWeAsk ? `q-why-${field.id}` : null, locked ? lockedId : null].filter(Boolean).join(' ') || undefined;
    const describedBy = [infoIds, hasError ? errorId : null].filter(Boolean).join(' ') || undefined;
    const questionLabel: QuestionLabel = useMemo(
        () => ({
            labelledBy,
            describedBy,
            infoIds,
            errorId: hasError ? errorId : undefined,
            requiredId: isAnswerable && isRequired ? requiredId : undefined,
            required: isAnswerable && isRequired,
            invalid: hasError,
            readOnly: locked
        }),
        [labelledBy, describedBy, infoIds, errorId, requiredId, isAnswerable, isRequired, hasError, locked]
    );
    useEffect(() => {
        const controls = groupRef.current?.querySelectorAll<HTMLElement>('input:not([type=hidden]), textarea, select, [role=radiogroup], [role=combobox]');
        controls?.forEach((control) => {
            // Only this question's own controls, not those of nested questions.
            if (control.closest('[data-question-wrapper]') !== groupRef.current) return;
            const describedBy = (control.getAttribute('aria-describedby') ?? '').split(' ').filter((id) => id && id !== errorId);
            // Read-only (a field rule locks the question), not disabled: the
            // control stays in the tab order and keeps its text contrast.
            // Native boxes take `readonly`; anything else is blocked below
            // (onClickCapture / onKeyDownCapture) and says so through aria-readonly.
            if (locked) {
                if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) control.readOnly = true;
                control.setAttribute('aria-readonly', 'true');
                control.setAttribute('data-rule-readonly', 'true');
            } else if (control.hasAttribute('data-rule-readonly')) {
                if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement) control.readOnly = false;
                control.removeAttribute('aria-readonly');
                control.removeAttribute('data-rule-readonly');
            }
            if (hasError) {
                control.setAttribute('aria-invalid', 'true');
                control.setAttribute('aria-describedby', [...describedBy, errorId].join(' '));
            } else {
                control.removeAttribute('aria-invalid');
                if (describedBy.length) control.setAttribute('aria-describedby', describedBy.join(' '));
                else control.removeAttribute('aria-describedby');
            }
        });
    });

    // A locked question's own buttons (options, the date and dropdown
    // triggers) do nothing. Text boxes are read-only natively and keep their
    // caret and selection.
    const isTextBox = (target: EventTarget) => target instanceof HTMLElement && !!target.closest('input, textarea');
    const blockClick = (event: MouseEvent) => {
        if (isTextBox(event.target)) return;
        event.preventDefault();
        event.stopPropagation();
    };
    // In a locked radio group the arrow keys still move focus from option to
    // option (as in any radio group), without choosing: the group's own handler
    // would choose, so it never sees them.
    const moveFocusInRadioGroup = (event: KeyboardEvent): boolean => {
        const step = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0;
        const target = event.target instanceof HTMLElement ? event.target.closest<HTMLElement>('[role=radio]') : null;
        const group = target?.closest<HTMLElement>('[role=radiogroup]');
        if (!step || !target || !group) return false;
        const radios = Array.from(group.querySelectorAll<HTMLElement>('[role=radio]'));
        const at = radios.indexOf(target);
        if (at < 0 || !radios.length) return false;
        event.preventDefault();
        event.stopPropagation();
        radios[(at + step + radios.length) % radios.length].focus();
        return true;
    };
    const blockKeys = (event: KeyboardEvent) => {
        if (isTextBox(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
        if (moveFocusInRadioGroup(event)) return;
        if (event.key === 'Enter' || event.key.length === 1 || event.key.startsWith('Arrow')) {
            event.preventDefault();
            event.stopPropagation();
        }
    };

    const content = (
        <>
            <div className="relative">
                <div className="relative flex flex-wrap items-baseline gap-x-2.5">
                    {/* Labels: weight and contrast carry the hierarchy, not size
                        (ratified 2026-07-08 against the form-redesign mocks). */}
                    {/* A question label, and a text block's own headings, are set in
                        the theme's title face when it has one (theme-root.ts). */}
                    <div className={`${isTextBlock ? `${TEXT_BLOCK_BODY_CLASSES} form-text-block` : `${tokens.labelClass} form-title-face [&_p]:inline`} ${HEADING_CLASSES}`} style={{ color: theme?.primary }}>
                        {/* The title alone (no required mark): it is the controls' accessible name. */}
                        <div id={titleId} className="contents" lang={contentLang}>
                            {parse(titleHtml)}
                        </div>
                        {isAnswerable && isRequired && (
                            <>
                                <span aria-hidden="true" style={{ color: requiredMarkColour(theme) }}>
                                    {' '}
                                    *
                                </span>
                                <span id={requiredId} className="sr-only">
                                    {' '}
                                    {t('FIELD.REQUIRED')}
                                </span>
                            </>
                        )}
                    </div>
                    {isAnswerable && !isRequired && !locked && <span className="form-note-accent text-[13px] font-normal text-black-700">{t('FIELD.OPTIONAL')}</span>}
                    {locked && (
                        <span id={lockedId} className="form-note-accent text-[13px] font-normal text-black-700">
                            {t('FIELD.READ_ONLY')}
                        </span>
                    )}
                </div>
                {resolvedDescription && (
                    <div id={`q-desc-${field.id}`} className="mt-1.5 max-w-[62ch] text-[15px] leading-relaxed text-black-700" lang={contentLang}>
                        {resolvedDescription}
                    </div>
                )}
                {whyWeAsk && (
                    // The reason sits against a rule in the theme's border colour
                    // (Leaflet: a 3px margin-note rule in the action colour), so
                    // it belongs to the form's palette, not the app's blue. A
                    // theme's highlight takes the rule and the label (theme-root.ts).
                    <p
                        id={`q-why-${field.id}`}
                        className={cn('mt-2 max-w-[62ch] text-[14px]', leaflet ? 'border-l-[3px] pl-2.5 leading-normal' : 'border-l-2 pl-3 leading-relaxed text-black-700')}
                        style={leaflet ? { borderColor: themed('--form-highlight-rule', theme?.secondary), color: softInk(theme) } : { borderColor: themed('--form-highlight-rule', theme?.tertiary ?? '#818CA0') }}
                    >
                        <span className="font-semibold" style={{ color: themed('--form-highlight-text', theme?.primary) }} lang={language}>
                            {t('QUESTION.WHY_WE_ASK')}
                        </span>{' '}
                        <span lang={contentLang}>{whyWeAsk}</span>
                    </p>
                )}
            </div>
            <RenderImage field={field} />
            <QuestionLabelContext.Provider value={hasControls ? questionLabel : null}>{children}</QuestionLabelContext.Provider>
            {/* Honest, non-alarmist validation: say what to do, not just that something is wrong,
                and avoid alarm colours/urgency (DESIGN.md §5). The message is set in the
                theme's ink (amber text fell under 4.5:1 on the tinted presets); the icon in
                danger red marks it as a problem without relying on the colour of the words. */}
            {hasError && (
                <div id={errorId} role="alert" className="mt-2 flex items-start gap-2 text-[15px] leading-snug font-medium" style={{ color: theme?.primary }}>
                    <AlertCircle className="mt-px h-[18px] w-[18px] shrink-0 text-[#C43D3D]" strokeWidth={2} aria-hidden="true" />
                    <span>{errorMessage || ruleMessage || serverMessage || t('FIELD.ANSWER_REQUIRED')}</span>
                </div>
            )}
        </>
    );

    return (
        <div
            className={cn(
                'relative',
                number ? 'grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline' : 'flex flex-col gap-1 lg:gap-2',
                // Wide centred pages hang the number outside the text measure.
                number && numbering?.hang && '@min-[880px]/page:block',
                tokens.divider && 'border-b pb-7',
                // A locked question (a field rule sets it or makes it read-only) keeps
                // its ink, and its box takes a quiet tint so it does not look editable.
                locked && '[&_[aria-expanded]]:bg-[#F3F4F6]! [&_[aria-haspopup]]:bg-[#F3F4F6]! [&_button]:cursor-default [&_input]:cursor-default [&_input]:bg-[#F3F4F6]! [&_textarea]:cursor-default [&_textarea]:bg-[#F3F4F6]!',
                // The field's edge (inputs, the date and dropdown triggers, the
                // option controls) in signal red while its error shows.
                hasError &&
                    '[&_[aria-expanded]]:border-(--invalid-edge)! [&_[aria-haspopup]]:border-(--invalid-edge)! [&_[data-choice-indicator]]:border-(--invalid-edge)! [&_input:not([type=checkbox])]:border-(--invalid-edge)! [&_textarea]:border-(--invalid-edge)!'
            )}
            style={{
                ...(tokens.divider ? { borderColor: (theme?.tertiary ?? '#818CA0') + '40' } : {}),
                ...(hasError ? { ['--invalid-edge' as string]: invalidEdge(theme) } : {})
            }}
            ref={groupRef}
            data-question-wrapper
            data-rule-locked={locked || undefined}
            onClickCapture={locked ? blockClick : undefined}
            onKeyDownCapture={locked ? blockKeys : undefined}
            data-invalid={hasError || undefined}
            id={field.id}
            // A question made of several controls with no group of their own is
            // a group named by the title. Single controls, radio groups and the
            // like carry the name themselves (useQuestionLabel); a group around
            // them too would make screen readers say the question twice.
            {...(hasControls && group
                ? {
                      role: 'group',
                      'aria-labelledby': labelledBy,
                      'aria-describedby': [isAnswerable && isRequired ? requiredId : null, describedBy].filter(Boolean).join(' ') || undefined
                  }
                : {})}
        >
            {number ? (
                <>
                    {/* The number is a reading aid; the group's name is the question. */}
                    <span
                        aria-hidden="true"
                        data-testid="question-number"
                        className={cn('text-[16px] leading-[1.4] tabular-nums', numbering?.hang && '@min-[880px]/page:absolute @min-[880px]/page:top-0 @min-[880px]/page:-left-16 @min-[880px]/page:w-12 @min-[880px]/page:text-right')}
                        style={numbering?.plain ? { fontWeight: 600, color: theme?.primary } : { fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numberColour }}
                    >
                        {number}
                    </span>
                    <div className="flex min-w-0 flex-col gap-1 lg:gap-2">{content}</div>
                </>
            ) : (
                content
            )}
        </div>
    );
}
