import { useEffect, useId, useRef, useState } from 'react';

import { Loader2 } from 'lucide-react';

import { useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FieldInput } from '@app/shadcn/components/ui/input';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useLookUpAddressMutation } from '@app/store/redux/form-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { AddressPart, AddressParts, AddressRule, NL, PART_MAX, canonicalNlPostcode, hasAnyPart, lookupKey, partProblems, pyStrip } from '@app/utils/address';
import { countryName, questionCountries } from '@app/utils/countries';
import { parseScopedFieldId } from '@app/utils/repeating-groups';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import { useEnterToNextQuestion } from './next-question';
import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

interface IAddressField {
    field: StandardFormFieldDto;
    slide?: StandardFormFieldDto;
    isBuilder?: boolean;
}

type Parts = Record<AddressPart, string>;
/** What the lookup says, for the line under the boxes (and the live region): nothing, or one of these. */
type LookupStatus = 'idle' | 'looking' | 'found' | 'found_kept' | 'not_found' | 'unavailable';

const EMPTY: Parts = { street: '', house_number: '', house_number_addition: '', postcode: '', city: '', country: '' };

/** The boxes as they start: the stored answer, else empty with the question's first country. */
function boxesFrom(stored: AddressParts | undefined, countries: string[]): Parts {
    const parts = { ...EMPTY, ...(stored ?? {}) } as Parts;
    return { ...parts, country: parts.country || countries[0] };
}

/** What is stored for the boxes: each part trimmed and in Unicode form C, a Dutch postcode in its stored form; parts left empty are left out. */
export function addressAnswerOf(parts: Parts): AddressParts {
    const answer: AddressParts = {};
    (Object.keys(parts) as AddressPart[]).forEach((part) => {
        let text = pyStrip(parts[part] ?? '').normalize('NFC');
        if (part === 'postcode' && parts.country === NL) text = canonicalNlPostcode(text) ?? text;
        if (text) answer[part] = text;
    });
    return answer;
}

const sameParts = (a: Parts, b: Parts) => (Object.keys(EMPTY) as AddressPart[]).every((part) => a[part] === b[part]);

/**
 * An address question: postcode, house number, an optional addition, street and city, and a country when the
 * question allows more than one. For a Dutch address with the lookup on, street and city are suggested from the
 * postcode and house number once the respondent leaves one of those two boxes (never on every key, never moving
 * focus, never over what the respondent typed in street or city). Every box stays an ordinary, editable box: the
 * lookup being off, down or finding nothing, or another country, only means they are typed. What happens is
 * said in a polite status line (and read out), never by colour alone.
 *
 * The answer holds only the parts that are given; a country alone is no answer (the box keeps it until another part is typed).
 */
function AddressFieldSection({ field, isBuilder }: IAddressField) {
    const { theme } = useFormState();
    const { formResponse, addFieldAddressAnswer, removeAnswer } = useFormResponse();
    const { t, language } = useRespondentLanguage();
    const onKeyDown = useEnterToNextQuestion(field);
    const locked = useFieldRuleStates().isLocked(field.id);
    const workspace = useAppSelector(selectWorkspace);
    const responderForm = useAppSelector(selectResponderForm);
    const [lookUp] = useLookUpAddressMutation();
    const countries = questionCountries(field);
    const stored = formResponse.answers?.[field.id]?.address;
    const [parts, setParts] = useState<Parts>(() => boxesFrom(stored, countries));
    const [status, setStatus] = useState<LookupStatus>('idle');
    const { label: question, group } = useQuestionLabel();
    const ids = useId();
    const idOf = (name: string) => `address-${name}-${field.id}-${ids}`.replace(/[^A-Za-z0-9_-]/g, '');
    const statusId = idOf('status');
    const fieldRadius = styleTokens(theme?.style).fieldRadius;

    // The latest of everything an answer from the lookup needs when it arrives.
    const latest = useRef({ parts, commit: (_next: Parts) => {} });
    const lastKey = useRef('');
    const request = useRef(0);
    const lookedUp = useRef<{ street: string; city: string } | null>(null);

    const commit = (next: Parts) => {
        const answer = addressAnswerOf(next);
        if (hasAnyPart(answer)) addFieldAddressAnswer(field.id, answer);
        else removeAnswer(field.id);
    };
    latest.current = { parts, commit };

    // Another answer arrives (a rule set it, the form was reset): show it, but never rewrite the boxes being typed in.
    const storedKey = JSON.stringify(stored ?? null);
    useEffect(() => {
        const next = boxesFrom(stored, countries);
        setParts((current) => (JSON.stringify(addressAnswerOf(current)) === storedKey || (!stored && !hasAnyPart(addressAnswerOf(current))) ? current : next));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [storedKey]);

    const lookupWanted = !isBuilder && !locked && field.properties?.addressLookup !== false && countries.includes(NL) && !!workspace?.id && !!responderForm?.formId;

    const finishLookup = (result: { status: 'found'; street: string; city: string } | { status: 'not_found' }) => {
        if (result.status !== 'found') {
            setStatus('not_found');
            return;
        }
        const current = latest.current.parts;
        // What the respondent typed themselves stays; what is empty, or is still the last lookup's, is replaced.
        const replace = (value: string, was: string | undefined) => !value || value === was;
        const fillStreet = replace(current.street, lookedUp.current?.street);
        const fillCity = replace(current.city, lookedUp.current?.city);
        const next = { ...current, street: fillStreet ? result.street : current.street, city: fillCity ? result.city : current.city };
        lookedUp.current = { street: result.street, city: result.city };
        setParts(next);
        latest.current.commit(next);
        setStatus(fillStreet && fillCity ? 'found' : 'found_kept');
    };

    const maybeLookUp = (current: Parts) => {
        if (!lookupWanted || current.country !== NL) return;
        const key = lookupKey(current.postcode, current.house_number);
        if (!key) return;
        const id = `${key.postcode} ${key.houseNumber}`;
        if (id === lastKey.current) return;
        lastKey.current = id;
        const mine = ++request.current;
        setStatus('looking');
        lookUp({ workspaceId: workspace!.id, formId: responderForm!.formId!, fieldId: parseScopedFieldId(field.id)?.childId ?? field.id, postcode: key.postcode, houseNumber: key.houseNumber })
            .unwrap()
            .then((result) => {
                if (mine === request.current) finishLookup(result);
            })
            .catch(() => {
                if (mine !== request.current) return;
                // the same two values may be tried again on the next blur
                lastKey.current = '';
                setStatus('unavailable');
            });
    };

    const change = (part: AddressPart) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        if (locked) return;
        const next = { ...parts, [part]: event.target.value };
        setParts(next);
        commit(next);
        if (part === 'postcode' || part === 'house_number' || part === 'country') {
            // a later answer belongs to what is typed now
            request.current++;
            setStatus('idle');
            if (part === 'country' && event.target.value !== NL) lookedUp.current = null;
        }
    };

    // Leaving the postcode box shows it as it is stored (1015cs -> 1015 CS) and may start the lookup.
    const leave = (part: 'postcode' | 'house_number') => () => {
        if (locked) return;
        let next = latest.current.parts;
        if (part === 'postcode' && next.country === NL) {
            const canonical = canonicalNlPostcode(next.postcode);
            if (canonical && canonical !== next.postcode) {
                next = { ...next, postcode: canonical };
                setParts(next);
            }
        }
        maybeLookUp(next);
    };

    const showProblems = !!question?.invalid && !isBuilder;
    const problems: Partial<Record<AddressPart, AddressRule>> = showProblems ? partProblems(addressAnswerOf(parts), countries) : {};
    const problemText = (part: AddressPart): string | undefined => {
        const rule = problems[part];
        if (!rule) return undefined;
        if (rule === 'too_long') return t('ADDRESS.ERR.TOO_LONG', { count: PART_MAX[part] });
        if (rule === 'country') return t('ADDRESS.ERR.COUNTRY');
        if (rule === 'required') return t(`ADDRESS.ERR.REQUIRED_${part.toUpperCase()}`);
        if (part === 'postcode') return t(parts.country === NL ? 'ADDRESS.ERR.FORMAT_POSTCODE_NL' : 'ADDRESS.ERR.FORMAT_POSTCODE');
        if (part === 'house_number') return t('ADDRESS.ERR.FORMAT_HOUSE_NUMBER');
        if (part === 'house_number_addition') return t('ADDRESS.ERR.FORMAT_ADDITION');
        if (part === 'country') return t('ADDRESS.ERR.COUNTRY');
        return t('ADDRESS.ERR.FORMAT_TEXT');
    };

    const dutch = parts.country === NL;
    const sorted = [...countries].sort((a, b) => countryName(a, language).localeCompare(countryName(b, language), language));
    const labelledBy = question?.labelledBy;

    const box = (part: AddressPart, config: { autoComplete: string; inputMode?: 'numeric' | 'text'; span: string; optional?: boolean; hint?: string; onBlur?: () => void; last?: boolean }) => {
        const id = idOf(part);
        const errorText = problemText(part);
        const errorId = errorText ? idOf(`error-${part}`) : undefined;
        return (
            <div className={`flex flex-col gap-1 ${config.span}`}>
                <label htmlFor={id} className="text-sm font-medium" style={{ color: theme?.primary }}>
                    {t(`ADDRESS.${part.toUpperCase()}`)}
                    {config.optional && <span className="font-normal text-black-700"> ({t('ADDRESS.OPTIONAL')})</span>}
                </label>
                <FieldInput
                    id={id}
                    type="text"
                    inputMode={config.inputMode}
                    autoComplete={config.autoComplete}
                    maxLength={PART_MAX[part] * 2}
                    value={parts[part]}
                    disabled={isBuilder}
                    // A field rule that locks the question: the boxes show it, and cannot be typed over.
                    readOnly={locked}
                    aria-readonly={locked || undefined}
                    aria-invalid={errorText ? true : undefined}
                    aria-describedby={errorId}
                    placeholder={config.hint ? t(config.hint) : undefined}
                    $formTheme={theme}
                    onChange={change(part)}
                    onBlur={config.onBlur}
                    onKeyDown={config.last ? onKeyDown : undefined}
                    className="min-h-12 min-w-0"
                />
                {errorText && (
                    <span id={errorId} className="text-sm leading-snug font-medium" style={{ color: theme?.primary }}>
                        {errorText}
                    </span>
                )}
            </div>
        );
    };

    const statusText =
        status === 'looking' ? t('ADDRESS.STATUS.LOOKING') : status === 'found' ? t('ADDRESS.STATUS.FOUND') : status === 'found_kept' ? t('ADDRESS.STATUS.FOUND_KEPT') : status === 'not_found' ? t('ADDRESS.STATUS.NOT_FOUND') : status === 'unavailable' ? t('ADDRESS.STATUS.UNAVAILABLE') : '';
    const lookupLine = lookupWanted && dutch ? t('ADDRESS.LOOKUP_HINT') : '';

    return (
        <div role="group" {...group} aria-labelledby={labelledBy} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
                {box('postcode', { autoComplete: 'postal-code', span: 'col-span-2 sm:col-span-2', hint: dutch ? 'ADDRESS.POSTCODE_EXAMPLE' : undefined, onBlur: leave('postcode') })}
                {box('house_number', { autoComplete: 'off', inputMode: dutch ? 'numeric' : 'text', span: 'sm:col-span-2', hint: dutch ? 'ADDRESS.HOUSE_NUMBER_EXAMPLE' : undefined, onBlur: leave('house_number') })}
                {box('house_number_addition', { autoComplete: 'off', span: 'sm:col-span-2', optional: true })}
                {box('street', { autoComplete: 'off', span: 'col-span-2 sm:col-span-3' })}
                {box('city', { autoComplete: 'address-level2', span: 'col-span-2 sm:col-span-3', last: countries.length < 2 })}
                {countries.length > 1 && (
                    <div className="col-span-2 flex flex-col gap-1 sm:col-span-3">
                        <label htmlFor={idOf('country')} className="text-sm font-medium" style={{ color: theme?.primary }}>
                            {t('ADDRESS.COUNTRY')}
                        </label>
                        <select
                            id={idOf('country')}
                            value={parts.country}
                            autoComplete="country"
                            disabled={isBuilder}
                            aria-readonly={locked || undefined}
                            aria-invalid={problems.country ? true : undefined}
                            aria-describedby={problems.country ? idOf('error-country') : undefined}
                            className="min-h-12 w-full border bg-white px-3 text-base lg:text-lg"
                            style={{ borderRadius: fieldRadius, borderColor: theme?.tertiary ?? '#818CA0', color: theme?.primary }}
                            onChange={change('country')}
                            onKeyDown={onKeyDown}
                        >
                            {sorted.map((code) => (
                                <option key={code} value={code}>
                                    {countryName(code, language)}
                                </option>
                            ))}
                        </select>
                        {problems.country && (
                            <span id={idOf('error-country')} className="text-sm leading-snug font-medium" style={{ color: theme?.primary }}>
                                {problemText('country')}
                            </span>
                        )}
                    </div>
                )}
            </div>
            <div className="flex min-h-5 flex-col gap-0.5">
                <p id={statusId} role="status" aria-live="polite" data-testid="address-status" className="flex items-center gap-2 text-sm leading-snug text-[#344054]">
                    {status === 'looking' && <Loader2 className="h-4 w-4 shrink-0 motion-safe:animate-spin" aria-hidden="true" />}
                    {statusText}
                </p>
                {!statusText && lookupLine && (
                    <span id={idOf('hint-lookup')} className="text-sm text-[#667085]">
                        {lookupLine}
                    </span>
                )}
            </div>
        </div>
    );
}

const AddressField = ({ field, slide, isBuilder = false }: IAddressField) =>
    isBuilder ? (
        <AddressFieldSection field={field} slide={slide} isBuilder />
    ) : (
        <QuestionWrapper field={field}>
            <AddressFieldSection field={field} slide={slide} />
        </QuestionWrapper>
    );

export default AddressField;
