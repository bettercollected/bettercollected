'use client';

import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/navigation';

import { useTranslation } from 'react-i18next';

import AppArt from '@app/components/ui/app-art';
import globalConstants from '@app/constants/global';
import { useAppTheme } from '@app/lib/app-theme-context';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { GreetingPeriod, WelcomeState, greetingPeriod, welcomeState } from '@app/lib/welcome-band';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceFormsQuery, useGetWorkspaceStatsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getEditFormURL } from '@app/utils/url-utils';
import NewFormButton from '@app/views/atoms/new-form-button';

const GREETING_KEYS: Record<GreetingPeriod, string> = {
    morning: 'STAFF.WELCOME.GREETING_MORNING',
    afternoon: 'STAFF.WELCOME.GREETING_AFTERNOON',
    evening: 'STAFF.WELCOME.GREETING_EVENING'
};

/**
 * The first thing on the forms dashboard: a plain greeting (the person's first name and the time
 * of day, in their language), one sentence about where things stand and one next step. What it
 * knows comes from requests the page already makes (the forms list and the workspace's pending
 * deletion requests): nothing extra is asked of the server. Compact on a phone, where the motif
 * is left out so the forms list stays in view.
 */
export default function WelcomeBand() {
    const { t } = useTranslation();
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);
    const { can } = useWorkspacePermissions();
    const pigment = useAppTheme() === 'pigment';
    const canCreateForms = can(WorkspacePermission.FORM_CREATE);
    const canEditForms = can(WorkspacePermission.FORM_EDIT);
    const canReviewRequests = can(WorkspacePermission.PRIVACY_MANAGE);

    // the same arguments as the list below, so this reads its cached answer instead of asking again
    const forms = useGetWorkspaceFormsQuery<any>({ workspace_id: workspace.id, published: false, page: 1, size: globalConstants.pageSize }, { skip: !workspace.id });
    const stats = useGetWorkspaceStatsQuery(workspace.id ?? '', { skip: !workspace.id || !canReviewRequests });

    // The hour is the browser's, known only after mount: the server renders the neutral greeting.
    const [period, setPeriod] = useState<GreetingPeriod | null>(null);
    useEffect(() => setPeriod(greetingPeriod(new Date().getHours())), []);

    const items: Array<StandardFormDto> = forms.data?.items ?? [];
    const state: WelcomeState = welcomeState({
        formsTotal: forms.isLoading || forms.isError || !forms.data ? undefined : (forms.data.total ?? items.length),
        // a draft the builder can open (imported forms and the old builder have no editor to go to)
        drafts: items.filter((form) => !form.isPublished && form.settings?.provider === 'self' && form.builderVersion === 'v2'),
        pendingRequests: stats.data?.deletionRequests?.pending,
        canEditForms,
        canReviewRequests
    });
    if (state.kind === 'loading') return null;

    // Pigment's shapes sit in a box on the right; the text column gives up that width, so a shape never meets the greeting
    // or the button (a long Dutch greeting wraps instead). Daybreak's art fills the band behind the text, as it always did.
    const textClearOfArt = pigment && state.kind !== 'no-forms' ? ' sm:max-w-[min(52ch,calc(100%_-_216px))] lg:max-w-[min(52ch,calc(100%_-_296px))]' : '';

    const name = (auth?.firstName ?? '').trim();
    const greeting = period ? t(GREETING_KEYS[period]) : t('STAFF.WELCOME.GREETING_NEUTRAL');
    const dashboard = `/${workspace.workspaceName}/dashboard`;

    let text: string | null = null;
    let action: React.ReactNode = null;
    switch (state.kind) {
        case 'no-forms':
            // only the greeting: the empty state below carries the one sentence and the one action
            break;
        case 'requests':
            text = t('STAFF.WELCOME.REQUESTS_TEXT', { count: state.count });
            action = (
                <Button size="medium" onClick={() => router.push(`${dashboard}/deletion-requests`)}>
                    {t('STAFF.WELCOME.REQUESTS_ACTION')}
                </Button>
            );
            break;
        case 'draft':
            text = state.count === 1 && state.title ? t('STAFF.WELCOME.DRAFT_TEXT', { title: state.title }) : t('STAFF.WELCOME.DRAFTS_TEXT', { count: state.count });
            action = (
                <Button size="medium" onClick={() => router.push(getEditFormURL(workspace, { formId: state.formId } as StandardFormDto))}>
                    {t('STAFF.WELCOME.DRAFT_ACTION')}
                </Button>
            );
            break;
        default:
            // someone who cannot create forms is not told to start one, and gets no empty action area
            text = canCreateForms ? t('STAFF.WELCOME.READY_TEXT') : t('STAFF.WELCOME.READY_VIEW_TEXT');
            action = canCreateForms ? <NewFormButton /> : null;
    }

    return (
        <section aria-labelledby="welcome-band-title" data-testid="welcome-band" data-state={state.kind} className={`relative mb-6 overflow-hidden rounded border border-hairline-strong bg-brand-tint ${state.kind === 'no-forms' ? '' : 'sm:min-h-[172px]'}`}>
            {/* the picture lives in the empty state below when there are no forms yet: once is enough */}
            {state.kind !== 'no-forms' && (
                <div className={pigment ? 'absolute inset-y-0 right-0 hidden w-[200px] sm:block lg:w-[280px]' : 'absolute inset-0 hidden sm:block'} aria-hidden="true">
                    <AppArt variant="band" />
                </div>
            )}
            <div className={`relative flex max-w-[52ch] flex-col items-start gap-2 sm:gap-3 ${state.kind === 'no-forms' ? 'px-4 py-3 sm:px-7 sm:py-5' : 'p-4 sm:p-7'}${textClearOfArt}`}>
                <h2 id="welcome-band-title" className="m-0 text-xl leading-tight font-semibold tracking-title text-ink sm:text-2xl">
                    {name ? t('STAFF.WELCOME.WITH_NAME', { greeting, name }) : greeting}
                </h2>
                {text && <p className="m-0 text-sm leading-relaxed text-copy sm:text-base">{text}</p>}
                {action && <div className="mt-1">{action}</div>}
            </div>
        </section>
    );
}
