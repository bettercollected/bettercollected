'use client';

import { ReactNode, useEffect, useMemo, useRef, useState } from 'react';

import { Plus, Trash2 } from 'lucide-react';
import { v4 } from 'uuid';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { GroupItemScopeContext } from '@app/store/jotai/group-item-scope';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { logicSourcesById } from '@app/utils/conditional-logic';
import {
    addGroupItem,
    canAddItem,
    canRemoveItem,
    ensureGroupItems,
    getDisplayedItemCount,
    getGroupChildren,
    getItemHeader,
    getItemHiddenChildIds,
    getRepeatSettings,
    ItemScope,
    removeGroupItem,
    scopedFieldId
} from '@app/utils/repeating-groups';
import { actionText } from '@app/utils/theme-contrast';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

import QuestionWrapper from './question-wrapper';

// Children render with a scoped id; their `index` is pushed out of range so
// the field components' "scroll to the next question on Enter" helpers never
// jump to an unrelated question of the page.
const CHILD_INDEX_OFFSET = 1_000_000;

function GroupItem({
    group,
    index,
    header,
    removable,
    onRemove,
    renderChild
}: {
    group: StandardFormFieldDto;
    index: number;
    header: string;
    removable: boolean;
    onRemove: () => void;
    renderChild: (child: StandardFormFieldDto) => ReactNode;
}) {
    const { formResponse } = useFormResponse();
    const { theme } = useFormState();
    const { t } = useRespondentLanguage();
    const children = getGroupChildren(group);
    const childIds = children.map((c) => c.id).join('|');
    // Stable per item, so the scoped answers view is memoised correctly.
    const scope: ItemScope = useMemo(() => ({ groupId: group.id, index, childIds: childIds ? childIds.split('|') : [] }), [group.id, index, childIds]);
    // A condition on a choice question elsewhere in the form reads its options.
    const logicSources = logicSourcesById(useAppSelector(selectForm)?.fields);
    const hidden = getItemHiddenChildIds(group, formResponse.answers, index, logicSources);
    const headingId = `group-item-${group.id}-${index}`;
    // One level under the page's own heading: the form title (h1), or the
    // Leaflet section bar (h2).
    const ItemHeading = styleTokens(theme?.style).key === 'leaflet' ? 'h3' : 'h2';

    return (
        <section aria-labelledby={headingId} className="flex flex-col gap-8 rounded-xl border bg-white/70 p-4 md:p-6" style={{ borderColor: (theme?.tertiary ?? '#818CA0') + '55' }}>
            <div className="flex items-center justify-between gap-3">
                <ItemHeading id={headingId} className="text-black-900 text-base font-semibold">
                    {header}
                </ItemHeading>
                {removable && (
                    <button type="button" onClick={onRemove} className="text-black-700 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm hover:bg-black/5" aria-label={t('GROUP.REMOVE_LABEL', { header })}>
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                        {t('GROUP.REMOVE')}
                    </button>
                )}
            </div>
            <GroupItemScopeContext.Provider value={scope}>
                {children
                    .filter((child) => !hidden.has(child.id))
                    .map((child) => (
                        <div key={child.id} className="min-w-0">
                            {renderChild({
                                ...child,
                                id: scopedFieldId(child.id, index),
                                index: CHILD_INDEX_OFFSET + (child.index ?? 0)
                            })}
                        </div>
                    ))}
            </GroupItemScopeContext.Provider>
        </section>
    );
}

/**
 * A repeating group as the respondent sees it: the group question once, then
 * one block per item with "Add another <item>" and "Remove" controls inside
 * the creator's limits. Each item's questions answer into that item.
 */
export default function RepeatingGroupField({ field, renderChild }: { field: StandardFormFieldDto; renderChild: (child: StandardFormFieldDto) => ReactNode }) {
    const { formResponse, setFormResponse } = useFormResponse();
    const { hiddenValues } = useHiddenFieldValues();
    const { theme } = useFormState();
    const standardForm = useAppSelector(selectForm);
    const { t } = useRespondentLanguage();
    const { minItems, maxItems } = getRepeatSettings(field);
    // The creator's item name as written; the default one in the respondent's language.
    const itemLabel = field.properties?.repeat?.itemLabel?.trim() || t('GROUP.ITEM');
    const answers = formResponse.answers ?? {};
    const count = getDisplayedItemCount(field, answers);

    // Keys keep each item's inputs attached to the right block when an
    // earlier item is removed.
    const [keys, setKeys] = useState<string[]>(() => Array.from({ length: count }, () => v4()));
    const itemKeys = Array.from({ length: count }, (_, i) => keys[i] ?? `item-${i}`);
    const lastAdded = useRef<number | null>(null);

    // The group was seen: record its (possibly empty) items so the submission
    // carries at least the minimum.
    useEffect(() => {
        setFormResponse((previous) => (previous.answers?.[field.id] ? previous : { ...previous, answers: ensureGroupItems(previous.answers, field) as any }));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [field.id]);

    useEffect(() => {
        if (lastAdded.current === null) return;
        const heading = document.getElementById(`group-item-${field.id}-${lastAdded.current}`);
        heading?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
        lastAdded.current = null;
    }, [count, field.id]);

    const add = () => {
        lastAdded.current = count;
        setFormResponse((previous) => ({ ...previous, answers: addGroupItem(previous.answers, field) as any }));
        setKeys([...itemKeys, v4()]);
    };

    const remove = (index: number) => {
        setFormResponse((previous) => ({ ...previous, answers: removeGroupItem(previous.answers, field, index) as any }));
        setKeys(itemKeys.filter((_, i) => i !== index));
    };

    const countError = formResponse.invalidFields?.[field.id]?.[0];
    const errorMessage = countError === 'MAX_ITEMS' ? t('GROUP.MAX_ITEMS', { count: maxItems }) : countError === 'MIN_ITEMS' ? t('GROUP.MIN_ITEMS', { count: minItems }) : '';
    const pipeContext = { slides: standardForm?.fields, answers, hiddenValues };
    const addable = canAddItem(field, answers);
    const removable = canRemoveItem(field, answers);

    return (
        // A group named by the question; each item is a section named by its heading.
        <QuestionWrapper field={field} errorMessage={errorMessage} group>
            <div className="mt-2 flex flex-col gap-4">
                {itemKeys.map((key, index) => (
                    <GroupItem key={key} group={field} index={index} header={getItemHeader(field, index, pipeContext, itemLabel)} removable={removable} onRemove={() => remove(index)} renderChild={renderChild} />
                ))}
                <div className="flex flex-wrap items-center gap-3">
                    <button
                        type="button"
                        onClick={add}
                        disabled={!addable}
                        className="inline-flex w-fit items-center gap-2 rounded-[8px] border px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                        style={{ borderColor: theme?.secondary ?? '#1649E2', color: actionText(theme) }}
                    >
                        <Plus className="h-4 w-4" aria-hidden="true" />
                        {count ? t('GROUP.ADD_ANOTHER', { item: itemLabel }) : t('GROUP.ADD', { item: itemLabel })}
                    </button>
                    <span className="text-black-700 text-xs" aria-live="polite">
                        {minItems === maxItems ? t('GROUP.ENTRIES', { count: maxItems }) : t('GROUP.ENTRIES_RANGE', { min: minItems, max: maxItems })} · {t('GROUP.ADDED', { count })}
                    </span>
                </div>
            </div>
        </QuestionWrapper>
    );
}
