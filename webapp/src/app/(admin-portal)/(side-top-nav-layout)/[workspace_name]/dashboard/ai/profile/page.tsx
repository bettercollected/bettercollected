'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { useAppSelector } from '@app/store/hooks';
import { useGetAIProfileQuery, useUpdateAIProfileMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const MAX_SECTION_CHARS = 8000;

const SECTIONS: Array<{ key: 'about' | 'guidelines' | 'compliance'; label: string; hint: string; placeholder: string }> = [
    {
        key: 'about',
        label: 'STAFF.AI_PROFILE.ABOUT',
        hint: 'STAFF.AI_PROFILE.ABOUT_HINT',
        placeholder: 'STAFF.AI_PROFILE.ABOUT_PLACEHOLDER'
    },
    {
        key: 'guidelines',
        label: 'STAFF.AI_PROFILE.GUIDELINES',
        hint: 'STAFF.AI_PROFILE.GUIDELINES_HINT',
        placeholder: 'STAFF.AI_PROFILE.GUIDELINES_PLACEHOLDER'
    },
    {
        key: 'compliance',
        label: 'STAFF.AI_PROFILE.COMPLIANCE',
        hint: 'STAFF.AI_PROFILE.COMPLIANCE_HINT',
        placeholder: 'STAFF.AI_PROFILE.COMPLIANCE_PLACEHOLDER'
    }
];

export default function AIProfilePage() {
    const { t } = useTranslation();
    const locale = useIntlLocale();
    const workspace = useAppSelector(selectWorkspace);
    const { can } = useWorkspacePermissions();
    const canManageAI = can(WorkspacePermission.AI_MANAGE);
    const { toast } = useToast();

    const { data, isLoading } = useGetAIProfileQuery(workspace?.id, { skip: !workspace?.id });
    const [updateProfile, { isLoading: isSaving }] = useUpdateAIProfileMutation();

    const [draft, setDraft] = useState({ about: '', guidelines: '', compliance: '' });
    const [dirty, setDirty] = useState(false);

    useEffect(() => {
        if (data && !dirty) {
            setDraft({ about: data.about ?? '', guidelines: data.guidelines ?? '', compliance: data.compliance ?? '' });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [data]);

    const handleSave = async () => {
        const response: any = await updateProfile({ workspace_id: workspace.id, body: draft });
        if (response.data) {
            setDirty(false);
            toast({ description: t('STAFF.AI_PROFILE.SAVED') });
        } else {
            toast({ description: t('STAFF.AI_PROFILE.SAVE_FAILED'), variant: 'destructive' });
        }
    };

    return (
        <div className="flex w-full max-w-[760px] flex-col gap-8 pb-10">
            <div className="flex flex-col gap-1.5">
                <p className="text-black-600 max-w-[62ch] text-sm leading-relaxed">
                    {t('STAFF.AI_PROFILE.INTRO')}
                </p>
            </div>

            {SECTIONS.map((section) => (
                <div key={section.key} className="flex flex-col gap-2">
                    <div className="flex items-baseline justify-between gap-3">
                        <label htmlFor={`ai-profile-${section.key}`} className="text-black-900 text-sm font-semibold">
                            {t(section.label)}
                        </label>
                        <span className="text-black-600 shrink-0 text-xs tabular-nums">
                            {draft[section.key].length.toLocaleString(locale)} / {MAX_SECTION_CHARS.toLocaleString(locale)}
                        </span>
                    </div>
                    <p className="text-black-600 text-xs leading-relaxed">{t(section.hint)}</p>
                    <textarea
                        id={`ai-profile-${section.key}`}
                        rows={6}
                        maxLength={MAX_SECTION_CHARS}
                        value={draft[section.key]}
                        placeholder={t(section.placeholder)}
                        disabled={!canManageAI || isLoading}
                        onChange={(e) => {
                            setDraft({ ...draft, [section.key]: e.target.value });
                            setDirty(true);
                        }}
                        className="border-control text-black-900 placeholder:text-black-600 focus:border-brand-500 w-full resize-y rounded-md border bg-white px-3.5 py-3 text-sm leading-relaxed outline-hidden transition duration-150 disabled:cursor-not-allowed disabled:opacity-60"
                    />
                </div>
            ))}

            {canManageAI ? (
                <div className="flex items-center gap-4">
                    <Button size="medium" variant="primary" isLoading={isSaving} disabled={!dirty} onClick={handleSave}>
                        {t('STAFF.AI_PROFILE.SAVE')}
                    </Button>
                    {dirty && <span className="text-black-600 text-xs">{t('STAFF.AI_PROFILE.UNSAVED')}</span>}
                </div>
            ) : (
                <p className="text-black-600 text-xs">{t('STAFF.AI_PROFILE.ONLY_ADMINS')}</p>
            )}
        </div>
    );
}
