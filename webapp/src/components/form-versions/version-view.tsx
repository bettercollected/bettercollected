'use client';

import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { FieldTypes, StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { buttonClassName } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormVersionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { questionTypeName } from '@app/utils/version-changes';
import { formVersionsUrl } from '@app/utils/response-urls';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

const link = buttonClassName({ variant: 'v2Button', size: 'sm', className: '' });

/**
 * One published version of a form, read-only: its pages and questions as an
 * outline (type, required, options, how many rules). Nothing in it can be
 * answered or saved. The form's content only; never an answer.
 */
export default function VersionView({ version }: { version: number }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { can, ready, formRevisionsUiEnabled } = useWorkspacePermissions();
    const workspaceId = workspace?.id ?? '';
    const formId = form?.formId ?? '';
    const allowed = formRevisionsUiEnabled && can(WorkspacePermission.FORM_READ);
    const { data, isLoading, isError, error } = useGetWorkspaceFormVersionQuery({ workspaceId, formId, version }, { skip: !allowed || !workspaceId || !formId });
    const back = formVersionsUrl(workspace?.workspaceName ?? '', formId);

    if (!ready) return <div className="px-4 md:px-10 lg:px-28" role="status" aria-live="polite" />;
    if (!allowed) {
        return (
            <div className="px-4 md:px-10 lg:px-28">
                <p role="status" className="text-black-700 text-sm">
                    {t('FORM_VERSIONS.DISABLED')}
                </p>
            </div>
        );
    }

    return (
        <div className="px-4 md:px-10 lg:px-28" data-testid="version-view">
            <section aria-labelledby="version-view-title" className="flex max-w-3xl flex-col gap-4">
                <Link href={back} className="text-black-700 hover:text-black-900 w-fit text-sm underline underline-offset-2">
                    {t('FORM_VERSIONS.VIEW_PAGE.BACK')}
                </Link>
                <div className="flex flex-col gap-1">
                    <h2 id="version-view-title" className="text-lg font-semibold">
                        {t('FORM_VERSIONS.VIEW_PAGE.TITLE', { n: version })}
                    </h2>
                    <p className="text-black-700 text-sm">{t('FORM_VERSIONS.VIEW_PAGE.INTRO')}</p>
                </div>
                {version > 1 && (
                    <div className="flex flex-wrap gap-2">
                        <Link href={`${back}/compare?from=${version - 1}&to=${version}`} className={link}>
                            {t('FORM_VERSIONS.VIEW_PAGE.COMPARE_WITH_PREVIOUS')}
                        </Link>
                    </div>
                )}
                {isLoading && (
                    <p role="status" className="text-black-700 text-sm">
                        {t('FORM_VERSIONS.LOADING')}
                    </p>
                )}
                {isError && (
                    <p role="alert" className="text-sm">
                        {(error as any)?.status === 404 ? t('FORM_VERSIONS.VIEW_PAGE.NOT_FOUND') : t('FORM_VERSIONS.LOAD_ERROR')}
                    </p>
                )}
                {data && <Outline form={data} />}
            </section>
        </div>
    );
}

function pagesOf(form: StandardFormDto): StandardFormFieldDto[] {
    const slides = (form.fields ?? []).filter((field) => !field.type || field.type === FieldTypes.SLIDE);
    if (slides.length > 0) return slides;
    // a first-generation form: its questions are one page
    return (form.fields ?? []).length > 0 ? [{ id: 'page-1', type: FieldTypes.SLIDE, properties: { fields: form.fields } } as unknown as StandardFormFieldDto] : [];
}

function Outline({ form }: { form: StandardFormDto }) {
    const { t } = useTranslation();
    const pages = pagesOf(form);
    return (
        <div className="flex flex-col gap-4">
            <h3 className="text-base font-medium">{extractPlain(form.title)}</h3>
            <ol className="flex flex-col gap-4">
                {pages.map((page, index) => {
                    const questions = (page.properties?.fields ?? []) as StandardFormFieldDto[];
                    return (
                        <li key={page.id ?? index} className="border-black-300 rounded border bg-white p-4">
                            <h4 className="font-medium">
                                {t('FORM_VERSIONS.VIEW_PAGE.PAGE', { n: index + 1 })}
                                {page.properties?.sectionTitle ? ` · ${page.properties.sectionTitle}` : ''}
                            </h4>
                            {questions.length === 0 ? (
                                <p className="text-black-700 mt-2 text-sm">{t('FORM_VERSIONS.VIEW_PAGE.NO_QUESTIONS')}</p>
                            ) : (
                                <ol className="mt-3 flex flex-col gap-3">
                                    {questions.map((question) => (
                                        <Question key={question.id} question={question} />
                                    ))}
                                </ol>
                            )}
                        </li>
                    );
                })}
            </ol>
        </div>
    );
}

function extractPlain(title: unknown): string {
    if (typeof title === 'string') return title;
    return '';
}

function Question({ question }: { question: StandardFormFieldDto }) {
    const { t } = useTranslation();
    const choices = (question.properties?.choices ?? []) as Array<{ id: string; value?: string; label?: string }>;
    const rules = (question.properties?.rules ?? []) as unknown[];
    const notes: string[] = [];
    if (question.type !== FieldTypes.CALCULATED && question.type !== FieldTypes.STATEMENT) notes.push(question.validations?.required ? t('FORM_VERSIONS.VIEW_PAGE.REQUIRED') : t('FORM_VERSIONS.VIEW_PAGE.OPTIONAL'));
    if (question.type === FieldTypes.CALCULATED) notes.push(t('FORM_VERSIONS.VIEW_PAGE.CALCULATED'));
    if (question.internal) notes.push(t('FORM_VERSIONS.VIEW_PAGE.INTERNAL'));
    if (rules.length > 0) notes.push(t('FORM_VERSIONS.VIEW_PAGE.RULES', { count: rules.length }));
    if (question.properties?.logic) notes.push(t('FORM_VERSIONS.VIEW_PAGE.LOGIC'));
    return (
        <li className="flex flex-col gap-1">
            <p className="text-sm font-medium">{extractTextfromJSON(question)}</p>
            <p className="text-black-700 text-xs">{[questionTypeName(t, question.type), ...notes].join(' · ')}</p>
            {choices.length > 0 && (
                <ul aria-label={t('FORM_VERSIONS.VIEW_PAGE.OPTIONS')} className="text-black-800 ml-4 list-disc text-sm">
                    {choices.map((choice) => (
                        <li key={choice.id}>{choice.value || choice.label}</li>
                    ))}
                </ul>
            )}
        </li>
    );
}
