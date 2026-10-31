'use client';

import { useEffect, useRef, useState } from 'react';

import { FieldRuleStates } from '@app/lib/field-rules';
import { hasFieldRules, useFieldRuleStates } from '@app/lib/hooks/use-field-rule-states';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { fieldTitleText } from '@app/utils/calculated-fields';

/** What the respondent can tell about one question of the page; a change of it is a change they see. */
interface Look {
    required: boolean;
    locked: boolean;
    title?: string;
    description?: string;
    filled: boolean;
}

/** At most this many changes are named in one message; the rest are counted. */
const NAMED_MAX = 3;

const withoutPipes = (text: string): string =>
    text
        .replace(/\{\{[^}]*\}\}/g, '')
        .replace(/\s+/g, ' ')
        .trim();

function lookOf(field: StandardFormFieldDto, states: FieldRuleStates): Look {
    const text = states.text(field.id);
    return {
        required: states.isRequired(field.id, !!field.validations?.required),
        locked: states.isLocked(field.id),
        title: text?.title,
        description: text?.description,
        filled: states.valued.has(field.id)
    };
}

const hasFocus = (fieldId: string): boolean => typeof document !== 'undefined' && document.activeElement?.closest('[data-question-wrapper]')?.id === fieldId;

/**
 * A polite status message for what a respondent's answer changed on this
 * page through the form's field rules: a question that is now required or
 * optional, read-only or filled in, reworded or given another description.
 * One message per change batch; nothing when the page first shows, and
 * nothing about the question the respondent is in (they hear its state
 * through the control itself). Renders nothing for a form without rules.
 */
export default function FieldRuleAnnouncer({ fields }: { fields: StandardFormFieldDto[] }) {
    const form = useAppSelector(selectResponderForm);
    return hasFieldRules(form?.fields) ? <Announcer fields={fields} /> : null;
}

function Announcer({ fields }: { fields: StandardFormFieldDto[] }) {
    const states = useFieldRuleStates();
    const { t } = useRespondentLanguage();
    const [message, setMessage] = useState('');
    const before = useRef<Map<string, Look> | null>(null);

    useEffect(() => {
        const now = new Map(fields.map((field) => [field.id, lookOf(field, states)] as const));
        const previous = before.current;
        before.current = now;
        // The first look is the baseline, not news.
        if (!previous) return;
        const lines: string[] = [];
        fields.forEach((field) => {
            const was = previous.get(field.id);
            const is = now.get(field.id)!;
            if (!was) return;
            const title = withoutPipes(is.title ?? fieldTitleText(field));
            const focused = hasFocus(field.id);
            if (is.title && is.title !== was.title) lines.push(t('FIELD_RULES.NOW_TITLED', { title }));
            if (is.description !== was.description && (is.description || was.description)) lines.push(t('FIELD_RULES.DESCRIPTION_CHANGED', { title }));
            if (focused) return;
            if (is.locked !== was.locked) lines.push(is.locked ? t(is.filled ? 'FIELD_RULES.NOW_FILLED_IN' : 'FIELD_RULES.NOW_READ_ONLY', { title }) : t('FIELD_RULES.NOW_EDITABLE', { title }));
            else if (!is.locked && is.required !== was.required) lines.push(t(is.required ? 'FIELD_RULES.NOW_REQUIRED' : 'FIELD_RULES.NOW_OPTIONAL', { title }));
        });
        if (!lines.length) return;
        const named = lines.slice(0, NAMED_MAX);
        if (lines.length > NAMED_MAX) named.push(t('FIELD_RULES.MORE', { count: lines.length - NAMED_MAX }));
        setMessage(named.join(' '));
    }, [states]);

    return (
        <div role="status" aria-live="polite" aria-atomic="true" className="sr-only" data-testid="field-rule-status">
            {message}
        </div>
    );
}
