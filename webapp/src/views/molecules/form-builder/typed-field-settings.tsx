'use client';

import { useEffect, useId, useState } from 'react';

import { ArrowUp, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { IFormFieldValidation } from '@app/models/types/form-builder-shared';
import { questionCurrencies } from '@app/utils/answer-rules';
import { CURRENCIES_MAX, CURRENCY_CODES } from '@app/utils/currency';
import { TAGS_MAX, TAG_LENGTH_MAX } from '@app/utils/tags';
import { isTime } from '@app/utils/time-of-day';

import { selectClass } from './condition-editor-shared';
import { NumberSetting } from './inspector-controls';

type PropertyPatch = { minTime?: string; maxTime?: string; currencies?: string[]; label?: string };

/** The window of a time question: its earliest and latest time (native time boxes; empty = no limit). */
function TimeWindowSettings({ field, onPropertyChange }: { field: StandardFormFieldDto; onPropertyChange: (patch: PropertyPatch) => void }) {
    const { t } = useTranslation('builder');
    const id = useId();
    const { minTime, maxTime } = field.properties ?? {};
    const backToFront = isTime(minTime) && isTime(maxTime) && minTime > maxTime;
    // The short label beside the time box ("Arrival time"), saved when the box is left.
    const [label, setLabel] = useState(field.properties?.label ?? '');
    useEffect(() => {
        setLabel(field.properties?.label ?? '');
    }, [field.id, field.properties?.label]);
    const box = (key: 'minTime' | 'maxTime', label: string, value: string | undefined) => (
        <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label htmlFor={`${id}-${key}`} className="text-xs text-black-700">
                {label}
            </label>
            <input
                id={`${id}-${key}`}
                type="time"
                value={value ?? ''}
                aria-invalid={backToFront || undefined}
                aria-describedby={`${id}-hint`}
                onChange={(event) => onPropertyChange({ [key]: event.target.value || undefined })}
                className={`h-8 w-full rounded border bg-white px-2 text-xs ${backToFront ? 'border-amber-500' : 'border-control focus:border-brand-500'}`}
            />
        </div>
    );
    return (
        <div className="flex flex-col gap-3" data-testid="time-window-settings">
            <label className="flex flex-col gap-1 text-xs text-black-700">
                {t('TYPED_SETTINGS.LABEL')}
                <input
                    className={selectClass}
                    value={label}
                    maxLength={120}
                    placeholder={t('TYPED_SETTINGS.LABEL_PLACEHOLDER')}
                    onChange={(event) => setLabel(event.target.value)}
                    onBlur={() => {
                        const next = label.trim();
                        if (next !== (field.properties?.label ?? '')) onPropertyChange({ label: next || undefined });
                    }}
                />
            </label>
            <div className="flex gap-2">
                {box('minTime', t('TYPED_SETTINGS.EARLIEST'), minTime)}
                {box('maxTime', t('TYPED_SETTINGS.LATEST'), maxTime)}
            </div>
            <p id={`${id}-hint`} role={backToFront ? 'status' : undefined} className={`text-[11px] leading-relaxed ${backToFront ? 'text-amber-700' : 'text-black-600'}`}>
                {backToFront ? t('TYPED_SETTINGS.TIME_ORDER') : t('TYPED_SETTINGS.TIME_HINT')}
            </p>
        </div>
    );
}

/**
 * The currencies a currency question offers (the first is the default) and
 * the lowest and highest amount, in whole units of the currency.
 */
function CurrencySettings({ field, onChange, onPropertyChange }: { field: StandardFormFieldDto; onChange: (patch: Partial<IFormFieldValidation>) => void; onPropertyChange: (patch: PropertyPatch) => void }) {
    const { t } = useTranslation('builder');
    const id = useId();
    const currencies = questionCurrencies(field);
    const rules = field.validations ?? {};
    const conflict = rules.minValue !== undefined && rules.maxValue !== undefined && rules.minValue > rules.maxValue;
    const available = CURRENCY_CODES.filter((code) => !currencies.includes(code));
    // the euro stands in when none is chosen: saving it as the list keeps what the respondent sees
    const save = (next: string[]) => onPropertyChange({ currencies: next.length ? next : undefined });
    return (
        <div className="flex flex-col gap-3" data-testid="currency-settings">
            <div className="flex flex-col gap-1.5">
                <div id={`${id}-title`} className="text-xs font-medium text-black-700">
                    {t('TYPED_SETTINGS.CURRENCIES')}
                </div>
                <ul aria-labelledby={`${id}-title`} className="flex flex-col gap-1">
                    {currencies.map((code, index) => (
                        <li key={code} className="flex items-center gap-1.5 rounded border border-black-300 bg-white px-2 py-1 text-xs">
                            <span className="font-medium text-black-800">{code}</span>
                            {index === 0 ? (
                                <span className="rounded bg-black-100 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-black-600 uppercase">{t('TYPED_SETTINGS.DEFAULT')}</span>
                            ) : (
                                <button type="button" className="ml-1 rounded p-1 text-black-600 hover:text-black-800" aria-label={t('TYPED_SETTINGS.MAKE_DEFAULT', { code })} title={t('TYPED_SETTINGS.MAKE_DEFAULT', { code })} onClick={() => save([code, ...currencies.filter((c) => c !== code)])}>
                                    <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                                </button>
                            )}
                            {currencies.length > 1 && (
                                <button type="button" className="ml-auto rounded p-1 text-black-600 hover:text-black-800" aria-label={t('TYPED_SETTINGS.REMOVE_CURRENCY', { code })} title={t('TYPED_SETTINGS.REMOVE_CURRENCY', { code })} onClick={() => save(currencies.filter((c) => c !== code))}>
                                    <X className="h-3.5 w-3.5" aria-hidden="true" />
                                </button>
                            )}
                        </li>
                    ))}
                </ul>
                {currencies.length < CURRENCIES_MAX && (
                    <>
                        <label htmlFor={`${id}-add`} className="sr-only">
                            {t('TYPED_SETTINGS.ADD_CURRENCY')}
                        </label>
                        <select id={`${id}-add`} className={selectClass} value="" onChange={(event) => event.target.value && save([...currencies, event.target.value])}>
                            <option value="">{t('TYPED_SETTINGS.ADD_CURRENCY')}</option>
                            {available.map((code) => (
                                <option key={code} value={code}>
                                    {code}
                                </option>
                            ))}
                        </select>
                    </>
                )}
                <p className="text-[11px] leading-relaxed text-black-600">{t('TYPED_SETTINGS.CURRENCY_HINT')}</p>
            </div>
            <div className="flex gap-2">
                <NumberSetting label={t('TYPED_SETTINGS.LOWEST_AMOUNT')} integer={false} step="any" placeholder={t('TYPED_SETTINGS.NO_LIMIT')} value={rules.minValue} onChange={(minValue) => onChange({ minValue })} invalid={conflict} />
                <NumberSetting label={t('TYPED_SETTINGS.HIGHEST_AMOUNT')} integer={false} step="any" placeholder={t('TYPED_SETTINGS.NO_LIMIT')} value={rules.maxValue} onChange={(maxValue) => onChange({ maxValue })} invalid={conflict} />
            </div>
            {conflict && (
                <p role="status" className="text-[11px] leading-relaxed text-amber-700">
                    {t('TYPED_SETTINGS.AMOUNT_ORDER')}
                </p>
            )}
        </div>
    );
}

/**
 * A tags question's limits: the fewest and the most tags (never above
 * TAGS_MAX) and the longest one tag may be (never above TAG_LENGTH_MAX).
 * Left empty, the caps themselves apply.
 */
function TagsSettings({ field, onChange }: { field: StandardFormFieldDto; onChange: (patch: Partial<IFormFieldValidation>) => void }) {
    const { t } = useTranslation('builder');
    const rules = field.validations ?? {};
    const conflict = rules.minChoices !== undefined && rules.maxChoices !== undefined && rules.minChoices > rules.maxChoices;
    // a number above the cap is brought back to it; 0 or less is no limit
    const clamp = (value: number | undefined, max: number) => (value === undefined || value < 1 ? undefined : Math.min(max, Math.trunc(value)));
    return (
        <div className="flex flex-col gap-3" data-testid="tags-settings">
            <div className="flex gap-2">
                <NumberSetting label={t('TYPED_SETTINGS.FEWEST_TAGS')} min={1} max={TAGS_MAX} placeholder={t('TYPED_SETTINGS.NO_LIMIT')} value={rules.minChoices} onChange={(minChoices) => onChange({ minChoices: clamp(minChoices, TAGS_MAX) })} invalid={conflict} />
                <NumberSetting label={t('TYPED_SETTINGS.MOST_TAGS')} min={1} max={TAGS_MAX} placeholder={t('TYPED_SETTINGS.NO_LIMIT')} value={rules.maxChoices} onChange={(maxChoices) => onChange({ maxChoices: clamp(maxChoices, TAGS_MAX) })} invalid={conflict} />
            </div>
            <div className="flex gap-2">
                <NumberSetting label={t('TYPED_SETTINGS.LONGEST_TAG')} min={1} max={TAG_LENGTH_MAX} placeholder={String(TAG_LENGTH_MAX)} value={rules.maxLength} onChange={(maxLength) => onChange({ maxLength: clamp(maxLength, TAG_LENGTH_MAX) })} />
            </div>
            {conflict && (
                <p role="status" className="text-[11px] leading-relaxed text-amber-700">
                    {t('TYPED_SETTINGS.TAGS_ORDER')}
                </p>
            )}
            <p className="text-[11px] leading-relaxed text-black-600">{t('TYPED_SETTINGS.TAGS_HINT', { most: TAGS_MAX, length: TAG_LENGTH_MAX })}</p>
        </div>
    );
}

/** The answer rules of the time, currency and tags types, in the builder's language (the day and date range types have only date rules). */
export default function TypedFieldSettings({ field, onChange, onPropertyChange }: { field: StandardFormFieldDto; onChange: (patch: Partial<IFormFieldValidation>) => void; onPropertyChange: (patch: PropertyPatch) => void }) {
    switch (field.type) {
        case 'time':
            return <TimeWindowSettings field={field} onPropertyChange={onPropertyChange} />;
        case 'currency':
            return <CurrencySettings field={field} onChange={onChange} onPropertyChange={onPropertyChange} />;
        case 'tags':
            return <TagsSettings field={field} onChange={onChange} />;
        default:
            return null;
    }
}
