'use client';

import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { RadioGroup, RadioGroupItem } from '@app/shadcn/components/ui/radio-group';
import { useGetPromotionTargetsQuery } from '@app/store/workspaces/form-promotion-api';

import type { TargetWorkspace } from './use-target-workspaces';

const CHOICE = 'flex min-h-[44px] cursor-pointer items-start gap-3 rounded border border-black-300 bg-white p-3 text-sm hover:bg-black-100 sm:min-h-[40px]';

export type Mode = 'new' | 'existing';

export interface WhereStepProps {
    /** The form being copied (its workspace and id): the picker lists what the person may update in the target. */
    source: { workspaceId: string; formId: string };
    workspaces: TargetWorkspace[];
    loading: boolean;
    failed: boolean;
    targetWorkspaceId: string;
    onTargetWorkspace: (id: string) => void;
    mode: Mode;
    onMode: (mode: Mode) => void;
    targetFormId: string;
    onTargetForm: (id: string, title: string) => void;
}

export default function WhereStep(props: WhereStepProps) {
    const { t } = useTranslation();
    const { workspaces, loading, failed, targetWorkspaceId, mode, targetFormId } = props;
    const chosen = workspaces.find((w) => w.id === targetWorkspaceId);
    const [search, setSearch] = useState('');
    const [query, setQuery] = useState('');
    // a request for each key press would meet the server's rate limit
    useEffect(() => {
        const timer = setTimeout(() => setQuery(search.trim()), 300);
        return () => clearTimeout(timer);
    }, [search]);

    const asking = mode === 'existing' && !!chosen;
    const targets = useGetPromotionTargetsQuery({ workspaceId: props.source.workspaceId, formId: props.source.formId, targetWorkspaceId, q: query || undefined }, { skip: !asking });

    return (
        <div className="flex flex-col gap-5">
            {loading && (
                <p role="status" className="text-sm text-black-700">
                    {t('FORM_PROMOTION.WHERE.LOADING_WORKSPACES')}
                </p>
            )}
            {!loading && failed && (
                <p role="alert" className="text-sm">
                    {t('FORM_PROMOTION.WHERE.WORKSPACES_ERROR')}
                </p>
            )}
            {!loading && !failed && workspaces.length === 0 && (
                <p role="status" className="text-sm">
                    {t('FORM_PROMOTION.WHERE.NO_WORKSPACES')}
                </p>
            )}

            {workspaces.length > 0 && (
                <fieldset className="flex flex-col gap-2">
                    <legend className="text-sm font-semibold">{t('FORM_PROMOTION.WHERE.WORKSPACE_LEGEND')}</legend>
                    <p id="promotion-workspace-hint" className="text-sm text-black-700">
                        {t('FORM_PROMOTION.WHERE.WORKSPACE_HINT')}
                    </p>
                    <RadioGroup aria-describedby="promotion-workspace-hint" value={targetWorkspaceId} onValueChange={props.onTargetWorkspace}>
                        {workspaces.map((workspace) => (
                            <label key={workspace.id} htmlFor={`promotion-workspace-${workspace.id}`} className={CHOICE}>
                                <RadioGroupItem id={`promotion-workspace-${workspace.id}`} value={workspace.id} className="mt-0.5 shrink-0" />
                                <span className="break-words">{workspace.title}</span>
                            </label>
                        ))}
                    </RadioGroup>
                </fieldset>
            )}

            {chosen && (
                <fieldset className="flex flex-col gap-2">
                    <legend className="text-sm font-semibold">{t('FORM_PROMOTION.WHERE.MODE_LEGEND')}</legend>
                    <RadioGroup value={mode} onValueChange={(value: string) => props.onMode(value as Mode)}>
                        <label htmlFor="promotion-mode-new" className={CHOICE}>
                            <RadioGroupItem id="promotion-mode-new" value="new" className="mt-0.5 shrink-0" />
                            <span className="flex flex-col">
                                <span>{t('FORM_PROMOTION.WHERE.MODE_NEW')}</span>
                                <span className="text-black-700">{t('FORM_PROMOTION.WHERE.MODE_NEW_HINT')}</span>
                            </span>
                        </label>
                        <label htmlFor="promotion-mode-existing" className={CHOICE}>
                            <RadioGroupItem id="promotion-mode-existing" value="existing" className="mt-0.5 shrink-0" />
                            <span className="flex flex-col">
                                <span>{t('FORM_PROMOTION.WHERE.MODE_EXISTING')}</span>
                                <span className="text-black-700">{t('FORM_PROMOTION.WHERE.MODE_EXISTING_HINT')}</span>
                            </span>
                        </label>
                    </RadioGroup>
                </fieldset>
            )}

            {asking && (
                <div className="flex flex-col gap-2">
                    <label htmlFor="promotion-search" className="text-sm font-semibold">
                        {t('FORM_PROMOTION.WHERE.SEARCH_LABEL', { workspace: chosen.title })}
                    </label>
                    <input
                        id="promotion-search"
                        type="search"
                        value={search}
                        maxLength={200}
                        autoComplete="off"
                        placeholder={t('FORM_PROMOTION.WHERE.SEARCH_PLACEHOLDER')}
                        onChange={(event) => setSearch(event.target.value)}
                        className="min-h-[44px] rounded border border-control bg-white px-3 text-sm sm:min-h-[40px]"
                    />
                    {targets.isFetching && (
                        <p role="status" className="text-sm text-black-700">
                            {t('FORM_PROMOTION.WHERE.TARGETS_LOADING')}
                        </p>
                    )}
                    {targets.isError && (
                        <p role="alert" className="text-sm">
                            {t('FORM_PROMOTION.WHERE.TARGETS_ERROR')}
                        </p>
                    )}
                    {!targets.isFetching && !targets.isError && targets.data && targets.data.items.length === 0 && (
                        <p role="status" className="text-sm">
                            {t('FORM_PROMOTION.WHERE.TARGETS_EMPTY')}
                        </p>
                    )}
                    {targets.data && targets.data.items.length > 0 && (
                        <fieldset className="flex flex-col gap-2">
                            <legend className="sr-only">{t('FORM_PROMOTION.WHERE.TARGETS_LABEL', { workspace: chosen.title })}</legend>
                            <RadioGroup value={targetFormId} onValueChange={(id: string) => props.onTargetForm(id, targets.data?.items.find((item) => item.formId === id)?.title ?? '')}>
                                {targets.data.items.map((item) => (
                                    <label key={item.formId} htmlFor={`promotion-form-${item.formId}`} className={CHOICE}>
                                        <RadioGroupItem id={`promotion-form-${item.formId}`} value={item.formId} className="mt-0.5 shrink-0" />
                                        <span className="flex flex-col break-words">
                                            <span>{item.title || t('FORM_PROMOTION.WHERE.UNTITLED')}</span>
                                            {item.copiedFromSource && <span className="text-black-700">{t('FORM_PROMOTION.WHERE.COPIED_FROM_HERE')}</span>}
                                        </span>
                                    </label>
                                ))}
                            </RadioGroup>
                            {targets.data.more && <p className="text-sm text-black-700">{t('FORM_PROMOTION.WHERE.TARGETS_MORE')}</p>}
                        </fieldset>
                    )}
                </div>
            )}
        </div>
    );
}
