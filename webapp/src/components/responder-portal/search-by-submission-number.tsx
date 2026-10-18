"use client";
import { FormEvent, useId, useState } from 'react';

import { useRouter } from 'next/navigation';
import { useTranslation } from 'react-i18next';

import InfoIcon from '@Components/icons/info.icon';

import { SearchIcon } from '@app/components/icons/search';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionByUUIDQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

/**
 * Find a submission by its receipt number. On the respondent's pages it is in
 * their language; on the team's dashboard (`audience="team"`) in the app's.
 */
const SearchBySubmissionNumber = ({ className, audience = 'respondent' }: { className?: string; audience?: 'respondent' | 'team' }) => {
    const respondent = useRespondentLanguage();
    const team = useTranslation('respondent');
    const { t } = audience === 'team' ? team : respondent;
    const language = audience === 'team' ? team.i18n.language : respondent.language;
    const workspace = useAppSelector(selectWorkspace);
    const [submissionNumber, setSubmissionNumber] = useState('');
    const [getSubmissionByUUID, { isLoading }] = useLazyGetWorkspaceSubmissionByUUIDQuery();
    const isCustomDomain = window?.location?.host !== window.PUBLIC_CONFIG?.FORM_DOMAIN;

    const [error, setError] = useState(false);
    const errorId = useId();

    const router = useRouter();

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (!submissionNumber) return;
        const response = await getSubmissionByUUID({
            workspace_id: workspace.id,
            submissionUUID: submissionNumber
        });
        if (response.data) {
            const submissionUrl = isCustomDomain ? `/submissions/uuid/${submissionNumber}/form` : `/${workspace.workspaceName}/submissions/uuid/${submissionNumber}/form`;
            router.push(submissionUrl);
        }
        if (response.error) {
            setError(true);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={className} lang={language}>
            {/* Fluid width — the parent column (sidebar) decides how wide. */}
            <div className="flex w-full flex-col items-center justify-center rounded bg-white px-6 py-8">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100" aria-hidden="true">
                    <SearchIcon className="text-brand-500" width={22} height={22} strokeWidth={2} />
                </div>

                <div className="mt-4">
                    <div className="h4-new text-black-800 text-center font-medium">{t('LOOKUP.TITLE')}</div>
                    <div className="p2-new text-black-700 mt-2 text-center!">{t('LOOKUP.HINT')}</div>
                </div>
                <div className="mt-4 flex w-full gap-4">
                    <AppInput
                        required={true}
                        value={submissionNumber}
                        onChange={(event) => {
                            setError(false);
                            setSubmissionNumber(event.target.value);
                        }}
                        placeholder={t('LOOKUP.PLACEHOLDER')}
                        aria-label={t('LOOKUP.LABEL')}
                        aria-invalid={error || undefined}
                        aria-describedby={error ? errorId : undefined}
                        className="w-full flex-1"
                    />

                    <button type="submit" aria-label={t('LOOKUP.SEARCH')} className="flex items-center justify-center rounded bg-action p-3 hover:bg-action-hover active:bg-action-pressed key-edge [--key-edge:var(--color-action-pressed)]">
                        <SearchIcon className="text-white" width={16} height={16} strokeWidth={2} />
                    </button>
                </div>
                {/* Announced when it appears, and describes the field it is about. */}
                <div className="mt-2 text-xs text-[#C43D3D]" aria-live="polite">
                    {error && (
                        <div id={errorId} className="flex gap-2">
                            {' '}
                            <span aria-hidden="true">
                                <InfoIcon className="text-[#C43D3D]" width={16} height={16} />
                            </span>
                            {t('LOOKUP.NOT_FOUND')}
                        </div>
                    )}
                </div>
            </div>
        </form>
    );
};

export default SearchBySubmissionNumber;
