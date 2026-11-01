'use client';

import { useEffect, useId, useState } from 'react';

import Link from 'next/link';

import { useAtomValue } from 'jotai';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { activeFieldAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderFieldsValue, useField, useFieldActions } from '@app/store/jotai/entity-hooks';
import { SourcePreview, useGetOptionListsQuery, usePreviewOptionSourceMutation } from '@app/store/option-lists/api';
import { useGetWorkspaceFormQuery, useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ANSWER_OPTIONS_MAX, OptionSource, answerSourceQuestions, isAnswersSource, parentCandidates, parentLabelsOf } from '@app/utils/option-sources';

import { selectClass } from './condition-editor-shared';

type Kind = 'own' | 'list' | 'form_answers';

const questionText = (field: StandardFormFieldDto | undefined, fallback: string): string => {
    const title = typeof field?.title === 'string' ? field.title : '';
    return title.trim() || fallback;
};

/**
 * Where a dropdown or multiple choice question takes its options from, in the inspector: its own options (the
 * default), a workspace list (optionally narrowed by an earlier question's answer through the items' groups), or
 * the answers given to a question of another form. Another form's answers are shown to everyone who opens the form,
 * so picking them asks for a plain confirmation first, and the panel says what the server leaves out. Only for a
 * question of a page: a question inside a group has no source. The section shows while the server takes sources
 * (`optionSourcesEnabled`, from the permissions answer); with it off, a source a question already has is listed
 * read-only. The server checks every save again (the saver must be allowed to read the other form's responses).
 */
export default function OptionSourceSettings() {
    const { t } = useBuilderTranslation();
    const baseId = useId();
    const { optionSourcesEnabled } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const builtForm = useAppSelector(selectForm);
    const activeFieldComponent = useAtomValue(activeFieldAtom);
    const field = useField(activeFieldComponent?.id);
    const { updateFieldProperty } = useFieldActions();
    // Only what this section reads, and only up to this question: typing in another question's title does not render it.
    const fieldId = field?.id;
    const around = useBuilderFieldsValue(
        (formFields) => aroundQuestion(formFields || [], fieldId),
        [fieldId],
        (a, b) => JSON.stringify(a) === JSON.stringify(b)
    );
    const slides = around.slides;
    const [preview] = usePreviewOptionSourceMutation();
    const [shown, setShown] = useState<SourcePreview | null>(null);
    const [labels, setLabels] = useState<string[] | null>(null);
    const [previewFailed, setPreviewFailed] = useState(false);
    const [draftForm, setDraftForm] = useState('');
    const [draftQuestion, setDraftQuestion] = useState('');
    const [confirmed, setConfirmed] = useState(false);

    const source = field?.properties?.optionSource;
    const kind: Kind = source?.kind === 'list' ? 'list' : source?.kind === 'form_answers' ? 'form_answers' : 'own';
    const [pending, setPending] = useState<Kind | null>(null);
    const shownKind: Kind = pending ?? kind;

    // a dropdown or multiple choice question that sits on a page (not inside a group)
    const onPage = around.onPage;
    const eligible = !!field && (field.type === FieldTypes.DROP_DOWN || field.type === FieldTypes.MULTIPLE_CHOICE) && !field.internal && onPage;
    const workspaceId = workspace?.id as string;
    const { data: lists } = useGetOptionListsQuery({ workspaceId }, { skip: !eligible || !workspaceId || !optionSourcesEnabled });
    const { data: formsPage } = useGetWorkspaceFormsQuery({ workspace_id: workspaceId, page: 1, size: 100 }, { skip: !eligible || !workspaceId || !optionSourcesEnabled || shownKind !== 'form_answers' });
    const otherForms = (formsPage?.items ?? []).filter((form) => form.formId && form.formId !== builtForm?.formId);
    const chosenFormId = isAnswersSource(source) ? source.formId : draftForm;
    const { data: chosenForm } = useGetWorkspaceFormQuery({ workspace_id: workspaceId, custom_url: chosenFormId as string }, { skip: !eligible || !workspaceId || !optionSourcesEnabled || shownKind !== 'form_answers' || !chosenFormId });
    const questionsOfForm = answerSourceQuestions(chosenForm);
    const parents = field ? parentCandidates(slides, field.id) : [];

    // What the source offers now: counts, never a value (the labels only when the creator asks).
    const sourceKey = JSON.stringify(source ?? null);
    useEffect(() => {
        setShown(null);
        setLabels(null);
        setPreviewFailed(false);
        if (!eligible || !source || !optionSourcesEnabled || !workspaceId) return;
        let cancelled = false;
        preview({ workspaceId, source, parentLabels: field ? parentLabelsOf(field, undefined, slides) : [], limit: 1 })
            .then((result: any) => {
                if (cancelled) return;
                if (result?.data) setShown(result.data);
                else setPreviewFailed(true);
            })
            .catch(() => !cancelled && setPreviewFailed(true));
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sourceKey, eligible, optionSourcesEnabled, workspaceId]);

    if (!eligible || !field) return null;
    if (!optionSourcesEnabled && !source) return null;
    const readOnly = !optionSourcesEnabled;

    const apply = (next: OptionSource | undefined) => {
        if (next) {
            // a question has its own options or a source, never both
            if ((field.properties?.choices ?? []).length) updateFieldProperty(field.id, 'choices', []);
            if (field.properties?.optionFilter) updateFieldProperty(field.id, 'optionFilter', undefined);
        }
        updateFieldProperty(field.id, 'optionSource', next);
    };

    const chooseKind = (next: Kind) => {
        if (next === kind) return setPending(null);
        if (next === 'own') {
            setPending(null);
            return apply(undefined);
        }
        // nothing is stored until a list or a form's question is picked
        setPending(next);
        setConfirmed(false);
    };

    const showLabels = async () => {
        if (!source) return;
        const result: any = await preview({ workspaceId, source, parentLabels: parentLabelsOf(field, undefined, slides), limit: 20 });
        setLabels(result?.data ? result.data.items.map((item: any) => item.label) : []);
    };

    const list = source?.kind === 'list' ? (lists ?? []).find((item) => item.id === source.listId) : undefined;
    const listsId = `${baseId}-list`;
    const parentId = `${baseId}-parent`;
    const formId = `${baseId}-form`;
    const questionId = `${baseId}-question`;
    const confirmId = `${baseId}-confirm`;
    const kindName = `${baseId}-kind`;

    return (
        <fieldset className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0" data-testid="option-source-settings" disabled={readOnly}>
            <legend className="sr-only">{t('SOURCES.SECTION')}</legend>
            {readOnly && (
                <p role="note" className="text-xs text-black-600">
                    {t('SOURCES.LOCKED')}
                </p>
            )}
            <div role="radiogroup" aria-label={t('SOURCES.WHERE')} className="flex flex-col gap-1.5 text-xs text-black-800">
                {(['own', 'list', 'form_answers'] as Kind[]).map((option) => (
                    <label key={option} className="flex items-start gap-2">
                        <input type="radio" name={kindName} checked={shownKind === option} onChange={() => chooseKind(option)} className="mt-0.5" />
                        <span>{t(`SOURCES.KIND.${option.toUpperCase()}`)}</span>
                    </label>
                ))}
            </div>

            {shownKind === 'list' && (
                <div className="flex flex-col gap-2">
                    <label htmlFor={listsId} className="text-xs text-black-700">
                        {t('SOURCES.LIST')}
                    </label>
                    <select
                        id={listsId}
                        className={selectClass}
                        value={source?.kind === 'list' ? (source.listId ?? '') : ''}
                        onChange={(event) => {
                            if (!event.target.value) return;
                            setPending(null);
                            apply({ kind: 'list', listId: event.target.value, ...(source?.kind === 'list' && source.parentFieldId ? { parentFieldId: source.parentFieldId } : {}) });
                        }}
                    >
                        <option value="">{t('SOURCES.PICK_LIST')}</option>
                        {(lists ?? []).map((item) => (
                            <option key={item.id} value={item.id}>
                                {item.name}
                            </option>
                        ))}
                    </select>
                    {(lists ?? []).length === 0 && optionSourcesEnabled && (
                        <p className="text-xs text-black-600">
                            {t('SOURCES.NO_LISTS')}{' '}
                            <Link className="underline" href={`/${workspace?.workspaceName}/dashboard/lists`}>
                                {t('SOURCES.MANAGE_LISTS')}
                            </Link>
                        </p>
                    )}
                    {source?.kind === 'list' && list && parents.length > 0 && (
                        <>
                            <label htmlFor={parentId} className="text-xs text-black-700">
                                {t('SOURCES.PARENT')}
                            </label>
                            <select id={parentId} className={selectClass} value={source.parentFieldId ?? ''} onChange={(event) => apply({ kind: 'list', listId: source.listId, ...(event.target.value ? { parentFieldId: event.target.value } : {}) })}>
                                <option value="">{t('SOURCES.NO_PARENT')}</option>
                                {parents.map((parent) => (
                                    <option key={parent.id} value={parent.id}>
                                        {questionText(parent, t('SOURCES.UNTITLED'))}
                                    </option>
                                ))}
                            </select>
                            <p className="text-[11px] leading-relaxed text-black-600">{t('SOURCES.PARENT_NOTE')}</p>
                        </>
                    )}
                </div>
            )}

            {shownKind === 'form_answers' && (
                <div className="flex flex-col gap-2">
                    <div role="note" className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs leading-relaxed text-amber-950">
                        <p className="font-semibold">{t('SOURCES.WARNING_TITLE')}</p>
                        <p>{t('SOURCES.WARNING')}</p>
                        <p className="mt-1">{t('SOURCES.WARNING_LEFT_OUT')}</p>
                    </div>
                    {isAnswersSource(source) ? (
                        <p className="text-xs text-black-700">
                            {t('SOURCES.FROM_ANSWERS', {
                                form: otherForms.find((form) => form.formId === source.formId)?.title || chosenForm?.title || t('SOURCES.UNTITLED_FORM'),
                                question: questionText(
                                    questionsOfForm.find((question) => question.id === source.questionId),
                                    t('SOURCES.UNTITLED')
                                )
                            })}
                        </p>
                    ) : (
                        <>
                            <label htmlFor={formId} className="text-xs text-black-700">
                                {t('SOURCES.FORM')}
                            </label>
                            <select
                                id={formId}
                                className={selectClass}
                                value={draftForm}
                                onChange={(event) => {
                                    setDraftForm(event.target.value);
                                    setDraftQuestion('');
                                }}
                            >
                                <option value="">{t('SOURCES.PICK_FORM')}</option>
                                {otherForms.map((form) => (
                                    <option key={form.formId} value={form.formId}>
                                        {form.title || t('SOURCES.UNTITLED_FORM')}
                                    </option>
                                ))}
                            </select>
                            {draftForm && (
                                <>
                                    <label htmlFor={questionId} className="text-xs text-black-700">
                                        {t('SOURCES.QUESTION')}
                                    </label>
                                    <select id={questionId} className={selectClass} value={draftQuestion} onChange={(event) => setDraftQuestion(event.target.value)}>
                                        <option value="">{t('SOURCES.PICK_QUESTION')}</option>
                                        {questionsOfForm.map((question) => (
                                            <option key={question.id} value={question.id}>
                                                {questionText(question, t('SOURCES.UNTITLED'))}
                                            </option>
                                        ))}
                                    </select>
                                    {questionsOfForm.length === 0 && <p className="text-xs text-black-600">{t('SOURCES.NO_QUESTIONS')}</p>}
                                </>
                            )}
                            <label htmlFor={confirmId} className="flex items-start gap-2 text-xs text-black-800">
                                <input id={confirmId} type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-0.5" />
                                <span>{t('SOURCES.CONFIRM')}</span>
                            </label>
                            <button
                                type="button"
                                disabled={!draftForm || !draftQuestion || !confirmed}
                                onClick={() => {
                                    setPending(null);
                                    apply({ kind: 'form_answers', formId: draftForm, questionId: draftQuestion });
                                }}
                                className="w-fit rounded-md bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                            >
                                {t('SOURCES.USE_ANSWERS')}
                            </button>
                        </>
                    )}
                </div>
            )}

            {source && (
                <div className="flex flex-col gap-1.5 text-xs text-black-700" aria-live="polite" data-testid="option-source-preview">
                    {previewFailed && <p className="text-amber-800">{t('SOURCES.PREVIEW_FAILED')}</p>}
                    {shown && !shown.available && <p className="text-amber-800">{t('SOURCES.GONE')}</p>}
                    {shown && shown.available && (
                        <>
                            <p>
                                {t('SOURCES.COUNTS', { count: shown.options })}
                                {source.kind === 'form_answers' ? ` ${t('SOURCES.COUNTS_RESPONSES', { count: shown.responses })}` : ''}
                            </p>
                            {shown.truncated && <p className="text-amber-800">{t('SOURCES.CUT', { count: ANSWER_OPTIONS_MAX })}</p>}
                            {shown.options === 0 && <p className="text-amber-800">{t('SOURCES.EMPTY')}</p>}
                            {shown.options > 0 && shown.options < 3 && <p className="text-black-600">{t('SOURCES.SMALL')}</p>}
                            {labels === null ? (
                                <button type="button" onClick={showLabels} className="w-fit underline">
                                    {t(source.kind === 'form_answers' ? 'SOURCES.SHOW_ANSWERS' : 'SOURCES.SHOW_ITEMS')}
                                </button>
                            ) : (
                                <ul className="m-0 list-disc pl-4">
                                    {labels.map((label) => (
                                        <li key={label}>{label}</li>
                                    ))}
                                </ul>
                            )}
                        </>
                    )}
                </div>
            )}
        </fieldset>
    );
}

/**
 * The questions before `fieldId` (a dependent list can follow one of them) and whether `fieldId` sits on a page, as
 * one synthetic page: ids, types, titles and options only.
 */
function aroundQuestion(slides: StandardFormFieldDto[], fieldId: string | undefined): { onPage: boolean; slides: StandardFormFieldDto[] } {
    const earlier: StandardFormFieldDto[] = [];
    for (const slide of slides) {
        for (const question of slide?.properties?.fields ?? []) {
            if (question.id === fieldId) return { onPage: true, slides: [{ id: 'earlier', index: 0, type: FieldTypes.SLIDE, properties: { fields: earlier } } as StandardFormFieldDto] };
            earlier.push({
                id: question.id,
                index: question.index,
                type: question.type,
                title: question.title,
                internal: question.internal,
                properties: { choices: question.properties?.choices, optionSource: question.properties?.optionSource }
            } as StandardFormFieldDto);
        }
    }
    return { onPage: false, slides: [] };
}
