'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { getGroupChildren, getRepeatSettings, REPEAT_COLUMNS_EXPORT_MAX, REPEAT_MAX_ITEMS_LIMIT } from '@app/utils/repeating-groups';
import { fieldText, selectClass } from './condition-editor-shared';

/**
 * Settings of a repeating group: how many items (min/max), what one item is
 * called (labels "Add another <item>"), the item header (may show a sibling
 * answer) and how exports lay the items out.
 */
export default function RepeatingGroupSettings({ field, slide }: { field: StandardFormFieldDto; slide: StandardFormFieldDto }) {
    const { t } = useTranslation('builder');
    const { updateGroupRepeat } = useBuilderActions();
    const settings = getRepeatSettings(field);
    const stored = field.properties?.repeat ?? {};
    const [minText, setMinText] = useState(String(settings.minItems));
    const [maxText, setMaxText] = useState(String(settings.maxItems));
    const [label, setLabel] = useState(stored.itemLabel ?? '');
    const [title, setTitle] = useState(stored.itemTitle ?? '');
    const [error, setError] = useState('');

    useEffect(() => {
        setMinText(String(settings.minItems));
        setMaxText(String(settings.maxItems));
        setLabel(stored.itemLabel ?? '');
        setTitle(stored.itemTitle ?? '');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [field.id, stored.minItems, stored.maxItems, stored.itemLabel, stored.itemTitle]);

    const save = (patch: Record<string, any>) => updateGroupRepeat(slide.index, field.id, patch);

    const saveLimits = () => {
        const min = Math.floor(Number(minText));
        const max = Math.floor(Number(maxText));
        if (!Number.isFinite(min) || !Number.isFinite(max) || min < 0 || max < 1 || max > REPEAT_MAX_ITEMS_LIMIT) {
            setError(t('GROUP_SETTINGS.ERR_RANGE', { max: REPEAT_MAX_ITEMS_LIMIT }));
            return;
        }
        if (min > max) {
            setError(t('GROUP_SETTINGS.ERR_ORDER'));
            return;
        }
        setError('');
        save({ minItems: min, maxItems: max });
    };

    const siblings = getGroupChildren(field).filter((c) => c.type !== FieldTypes.TEXT);
    const autoLayout = settings.maxItems <= REPEAT_COLUMNS_EXPORT_MAX ? 'columns' : 'rows';

    return (
        <div className="border-black-300 flex flex-col gap-3 border-t pt-4">
            <div>
                <div className="text-black-700 text-xs font-medium">{t('GROUP_SETTINGS.TITLE')}</div>
                <div className="text-black-600 text-[11px]">{t('GROUP_SETTINGS.INTRO')}</div>
            </div>
            <label className="text-black-700 flex flex-col gap-1 text-xs">
                {t('GROUP_SETTINGS.ITEM_CALLED')}
                <input className={selectClass} value={label} placeholder={t('GROUP_SETTINGS.ITEM_PLACEHOLDER')} maxLength={80} onChange={(e) => setLabel(e.target.value)} onBlur={() => save({ itemLabel: label.trim() || undefined })} />
                <span className="text-black-600 text-[11px]">{t('GROUP_SETTINGS.ADD_BUTTON', { item: settings.itemLabel })}</span>
            </label>
            <div className="flex gap-2">
                <label className="text-black-700 flex flex-1 flex-col gap-1 text-xs">
                    {t('GROUP_SETTINGS.AT_LEAST')}
                    <input className={selectClass} type="number" min={0} max={REPEAT_MAX_ITEMS_LIMIT} value={minText} onChange={(e) => setMinText(e.target.value)} onBlur={saveLimits} />
                </label>
                <label className="text-black-700 flex flex-1 flex-col gap-1 text-xs">
                    {t('GROUP_SETTINGS.AT_MOST')}
                    <input className={selectClass} type="number" min={1} max={REPEAT_MAX_ITEMS_LIMIT} value={maxText} onChange={(e) => setMaxText(e.target.value)} onBlur={saveLimits} />
                </label>
            </div>
            {error && <span className="text-[11px] text-amber-700">{error}</span>}
            <label className="text-black-700 flex flex-col gap-1 text-xs">
                {t('GROUP_SETTINGS.ITEM_HEADER')}
                <input className={selectClass} value={title} placeholder={t('GROUP_SETTINGS.ITEM_HEADER_PLACEHOLDER')} maxLength={300} onChange={(e) => setTitle(e.target.value)} onBlur={() => save({ itemTitle: title.trim() || undefined })} />
                <span className="text-black-600 text-[11px]">
                    {t('GROUP_SETTINGS.HEADER_HINT', { item: settings.itemLabel })}
                </span>
                {siblings.length > 0 && (
                    <select
                        className={selectClass}
                        aria-label={t('GROUP_SETTINGS.INSERT_ANSWER')}
                        value=""
                        onChange={(e) => {
                            if (!e.target.value) return;
                            const next = `${title}${title && !title.endsWith(' ') ? ' ' : ''}{{field:${e.target.value}}}`;
                            setTitle(next);
                            save({ itemTitle: next });
                        }}
                    >
                        <option value="">{t('GROUP_SETTINGS.INSERT_ANSWER_OPTION')}</option>
                        {siblings.map((c) => (
                            <option key={c.id} value={c.id}>
                                {fieldText(c)}
                            </option>
                        ))}
                    </select>
                )}
            </label>
            <label className="text-black-700 flex flex-col gap-1 text-xs">
                {t('GROUP_SETTINGS.IN_EXPORTS')}
                <select className={selectClass} value={stored.exportLayout ?? ''} onChange={(e) => save({ exportLayout: (e.target.value || undefined) as any })}>
                    <option value="">{t('GROUP_SETTINGS.AUTOMATIC', { layout: autoLayout === 'columns' ? t('GROUP_SETTINGS.LAYOUT_COLUMNS_SHORT') : t('GROUP_SETTINGS.LAYOUT_TABLE_SHORT') })}</option>
                    <option value="columns">{t('GROUP_SETTINGS.LAYOUT_COLUMNS')}</option>
                    <option value="rows">{t('GROUP_SETTINGS.LAYOUT_ROWS')}</option>
                </select>
            </label>
        </div>
    );
}
