'use client';

import { FormEvent, useState } from 'react';

import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { useGetEmbedSettingsQuery, useUpdateEmbedSettingsMutation } from '@app/store/workspaces/embed-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { embedErrorKey } from '@app/utils/form-embed';

/**
 * Workspace settings, "Embedding": the sites that may show the workspace's forms in a frame (docs/embed.md).
 * Owners and admins (workspace.manage) only, and only while this server has the feature on; the sidebar
 * item is hidden under the same two conditions. A change is saved at once (the whole list is replaced).
 */
export default function EmbeddingSettings() {
    const { t } = useTranslation();
    const { can, ready, formEmbedEnabled } = useWorkspacePermissions();

    if (!ready) return <div className="px-5 py-6 text-sm text-black-600 lg:px-10">{t('STAFF.EMBED.LOADING')}</div>;
    if (!can(WorkspacePermission.WORKSPACE_MANAGE)) return <p className="px-5 py-6 text-sm text-black-700 lg:px-10">{t('STAFF.EMBED.ONLY_ADMINS')}</p>;
    if (!formEmbedEnabled) return <p className="px-5 py-6 text-sm text-black-700 lg:px-10">{t('STAFF.EMBED.TURNED_OFF')}</p>;
    return <AllowedSites />;
}

function AllowedSites() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const settings = useGetEmbedSettingsQuery(workspace?.id as string, { skip: !workspace?.id });
    const [update, { isLoading: saving }] = useUpdateEmbedSettingsMutation();
    const [draft, setDraft] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);

    const origins = settings.data?.origins ?? [];
    const max = settings.data?.maxOrigins ?? 20;

    const save = async (next: string[]): Promise<boolean> => {
        setError(null);
        setNotice(null);
        const response = await update({ workspaceId: workspace.id as string, origins: next });
        if ('error' in response && response.error) {
            setError(t(embedErrorKey(response.error), { max }));
            return false;
        }
        setNotice(t('STAFF.EMBED.SAVED'));
        return true;
    };

    const add = async (event: FormEvent) => {
        event.preventDefault();
        const value = draft.trim();
        if (!value) return;
        if (await save([...origins, value])) setDraft('');
    };

    const remove = (origin: string) => save(origins.filter((item) => item !== origin));

    return (
        <div className="flex w-full max-w-[720px] flex-col gap-8 px-5 py-6 lg:px-10">
            <p className="max-w-[62ch] text-sm leading-relaxed text-black-600">{t('STAFF.EMBED.PAGE_INTRO')}</p>

            <section aria-labelledby="embed-list" className="flex flex-col gap-3">
                <div className="flex items-baseline justify-between gap-3">
                    <h2 id="embed-list" className="text-base font-semibold text-black-900">
                        {t('STAFF.EMBED.LIST_LABEL')}
                    </h2>
                    <span className="text-xs text-black-600">{t('STAFF.EMBED.COUNT', { count: origins.length, max })}</span>
                </div>
                {settings.isLoading ? (
                    <p role="status" className="text-sm text-black-600">
                        {t('STAFF.EMBED.LOADING')}
                    </p>
                ) : settings.isError ? (
                    <p role="alert" className="text-sm text-[#C43D3D]">
                        {t('STAFF.EMBED.LOAD_FAILED')}
                    </p>
                ) : origins.length === 0 ? (
                    <p className="text-sm text-black-700">{t('STAFF.EMBED.NONE')}</p>
                ) : (
                    <ul className="flex flex-col divide-y divide-black-300 rounded border border-black-300 bg-white">
                        {origins.map((origin) => (
                            <li key={origin} className="flex items-center justify-between gap-3 px-3 py-2">
                                <span className="min-w-0 truncate font-mono text-[13px] text-black-800">{origin}</span>
                                <button
                                    type="button"
                                    disabled={saving}
                                    aria-label={t('STAFF.EMBED.REMOVE_ARIA', { site: origin })}
                                    onClick={() => remove(origin)}
                                    className="shrink-0 rounded p-1.5 text-black-600 transition-colors hover:bg-black-100 hover:text-black-800 disabled:opacity-50"
                                >
                                    <X className="h-4 w-4" aria-hidden="true" />
                                </button>
                            </li>
                        ))}
                    </ul>
                )}

                <form onSubmit={add} className="flex flex-col gap-2" noValidate>
                    <label htmlFor="embed-site" className="text-sm font-medium text-black-700">
                        {t('STAFF.EMBED.ADD_LABEL')}
                    </label>
                    <div className="flex flex-col gap-2 sm:flex-row">
                        <AppInput
                            id="embed-site"
                            value={draft}
                            inputMode="url"
                            autoComplete="off"
                            spellCheck={false}
                            placeholder={t('STAFF.EMBED.ADD_PLACEHOLDER')}
                            aria-invalid={error ? true : undefined}
                            aria-describedby={error ? 'embed-site-error' : undefined}
                            className={`w-full font-mono text-sm! ${error ? 'border-[#C43D3D]!' : ''}`}
                            onChange={(event) => {
                                setDraft(event.target.value);
                                setError(null);
                                setNotice(null);
                            }}
                        />
                        <Button type="submit" size="medium" variant="primary" disabled={saving || !draft.trim() || origins.length >= max} className="shrink-0">
                            {t('STAFF.EMBED.ADD_BUTTON')}
                        </Button>
                    </div>
                    {error && (
                        <p id="embed-site-error" role="alert" className="text-sm text-[#C43D3D]">
                            {error}
                        </p>
                    )}
                    <p role="status" className="min-h-5 text-sm text-black-600">
                        {notice}
                    </p>
                </form>
            </section>

            <section className="flex flex-col gap-2">
                <h2 className="text-base font-semibold text-black-900">{t('STAFF.EMBED.FORMAT_TITLE')}</h2>
                <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed text-black-700">
                    <li>{t('STAFF.EMBED.FORMAT_ADDRESS')}</li>
                    <li>{t('STAFF.EMBED.FORMAT_WILDCARD')}</li>
                    <li>{t('STAFF.EMBED.FORMAT_LOCAL')}</li>
                </ul>
            </section>

            <section className="flex flex-col gap-2">
                <h2 className="text-base font-semibold text-black-900">{t('STAFF.EMBED.LEARNS_TITLE')}</h2>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.EMBED.LEARNS_TEXT')}</p>
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.EMBED.SIGN_IN_NOTE')}</p>
            </section>
        </div>
    );
}
