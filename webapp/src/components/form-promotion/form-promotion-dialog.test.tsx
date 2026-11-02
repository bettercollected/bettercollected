// "Copy to another workspace": the three steps, every refusal the server can answer with its sentence (English and
// Dutch), the retention confirmation, and what the dialog never does (ask anything before it is opened). The server
// is stood in for by the hooks of the API slice; the data is made up.
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import commonNl from '../../../public/locales/nl/common.json';
import FormPromotionDialog from './form-promotion-dialog';
import { PROMOTION_FAILURES, failureKey, failureOf, whereOf } from './promotion-errors';

const served = vi.hoisted(() => ({
    workspaces: [] as any[],
    targets: { items: [] as any[], more: false } as any,
    targetsCalls: [] as any[],
    previewCalls: [] as any[],
    applyCalls: [] as any[],
    preview: (() => Promise.resolve({})) as (arg: any) => Promise<any>,
    apply: (() => Promise.resolve({})) as (arg: any) => Promise<any>
}));

vi.mock('./use-target-workspaces', () => ({ useTargetWorkspaces: () => ({ workspaces: served.workspaces, loading: false, failed: false }) }));
vi.mock('@app/store/workspaces/form-promotion-api', async (original) => ({
    ...((await original()) as object),
    useGetPromotionTargetsQuery: (args: unknown, options: any) => {
        served.targetsCalls.push({ args, options });
        return options?.skip ? { data: undefined, isFetching: false, isError: false } : { data: served.targets, isFetching: false, isError: false };
    },
    usePreviewPromotionMutation: () => [
        (arg: any) => {
            served.previewCalls.push(arg);
            return { unwrap: () => served.preview(arg) };
        },
        { isLoading: false }
    ],
    useApplyPromotionMutation: () => [
        (arg: any) => {
            served.applyCalls.push(arg);
            return { unwrap: () => served.apply(arg) };
        },
        { isLoading: false }
    ]
}));

const workspace = { id: 'ws-src', workspaceName: 'voorbeeld-acceptatie', title: 'Voorbeeld Acceptatie' } as any;
const form = { formId: 'f-src', title: 'Aanmelding vrijwilligers' } as any;
const production = { id: 'ws-prod', title: 'Voorbeeld Productie', workspaceName: 'voorbeeld-productie' };

const goodPreview = (extra: Record<string, unknown> = {}) => ({
    valid: true,
    errors: [],
    warnings: [],
    created: true,
    diff: null,
    counts: { pages: 2, questions: 7 },
    notCarried: { webhooks: 2, emailActions: 1, sheets: 0, registrations: 1 },
    alsoNotCopied: ['responses'],
    adjusted: { counts: { imagesDropped: 3, listsMatchedByName: 2, logoFileNotCopied: 1 }, patternsDropped: [], listsMatchedByName: [], listsNotFound: [], answerSourcesDropped: [], shareAsChoicesOff: [], trustKept: [] },
    copyIsRestricted: false,
    sourceEtag: '"s1"',
    targetEtag: null,
    targetChangedSinceLastPromotion: false,
    retentionShortened: false,
    ...extra
});

const existingPreview = (extra: Record<string, unknown> = {}) =>
    goodPreview({
        created: false,
        targetEtag: '"t1"',
        diff: {
            changed: true,
            truncated: false,
            entries: [
                { kind: 'form_title_changed', scope: 'form', params: { before: 'Oud', after: 'Aanmelding vrijwilligers' } },
                { kind: 'question_added', scope: 'question', ref: 'q9', title: 'Telefoonnummer', params: { type: 'short_text' } }
            ]
        },
        ...extra
    });

const reject = (status: number, data: unknown) => Promise.reject({ status, data });

let closed: ReturnType<typeof vi.fn>;
const open = () => {
    closed = vi.fn();
    return render(<FormPromotionDialog open onOpenChange={closed} workspace={workspace} form={form} />);
};

const goToReview = async (existing = false) => {
    fireEvent.click(await screen.findByRole('radio', { name: 'Voorbeeld Productie' }));
    if (existing) {
        fireEvent.click(screen.getByRole('radio', { name: /An existing form/ }));
        fireEvent.click(await screen.findByRole('radio', { name: /Zorgvuldig formulier/ }));
    }
    fireEvent.click(screen.getByRole('button', { name: 'Review' }));
    await screen.findByRole('heading', { name: 'Review' });
};

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
});

beforeEach(() => {
    served.workspaces = [production, { id: 'ws-test', title: 'Voorbeeld Test', workspaceName: 'voorbeeld-test' }];
    served.targets = {
        items: [
            { formId: 'f-old', title: 'Zorgvuldig formulier', copiedFromSource: true },
            { formId: 'f-other', title: 'Ander formulier', copiedFromSource: false }
        ],
        more: false
    };
    served.targetsCalls = [];
    served.previewCalls = [];
    served.applyCalls = [];
    served.preview = () => Promise.resolve(goodPreview());
    served.apply = () => Promise.resolve({ formId: 'f-new', workspaceId: 'ws-prod', created: true, etag: '"n"', adjusted: {} });
});

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('step 1, where to', () => {
    it('lists the workspaces it was given, names the step and starts with Review off', async () => {
        open();
        const dialog = screen.getByRole('dialog', { name: 'Copy to another workspace' });
        expect(within(dialog).getByText('Step 1 of 3')).toBeInTheDocument();
        expect(within(dialog).getByRole('heading', { name: 'Where to' })).toBeInTheDocument();
        expect(
            within(dialog)
                .getAllByRole('radio')
                .map((r) => r.getAttribute('id'))
        ).toEqual(['promotion-workspace-ws-prod', 'promotion-workspace-ws-test']);
        expect(within(dialog).getByRole('button', { name: 'Review' })).toBeDisabled();
        // nothing is asked of the server before a workspace and a way are chosen
        expect(served.previewCalls).toEqual([]);
        expect(served.targetsCalls.every((c) => c.options?.skip)).toBe(true);
    });

    it('takes focus to the step heading when it opens', async () => {
        open();
        await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Where to' })));
    });

    it('says so when the person has no other workspace to create in', async () => {
        served.workspaces = [];
        open();
        expect(screen.getByText('You have no other workspace where you can create forms.')).toBeInTheDocument();
    });

    it('offers a new form, or an existing one from the list with search', async () => {
        open();
        fireEvent.click(screen.getByRole('radio', { name: 'Voorbeeld Productie' }));
        expect(screen.getByRole('button', { name: 'Review' })).toBeEnabled();
        fireEvent.click(screen.getByRole('radio', { name: /An existing form/ }));
        // an existing form must be picked
        expect(screen.getByRole('button', { name: 'Review' })).toBeDisabled();
        const search = screen.getByRole('searchbox', { name: 'Search forms in Voorbeeld Productie' });
        expect(screen.getByRole('radio', { name: /Zorgvuldig formulier/ })).toBeInTheDocument();
        expect(screen.getByText('Copied from this form')).toBeInTheDocument();
        fireEvent.change(search, { target: { value: 'Ander' } });
        await waitFor(() => expect(served.targetsCalls.some((c) => c.args.q === 'Ander')).toBe(true));
        expect(served.targetsCalls.at(-1).args).toMatchObject({ workspaceId: 'ws-src', formId: 'f-src', targetWorkspaceId: 'ws-prod' });
        fireEvent.click(screen.getByRole('radio', { name: /Ander formulier/ }));
        expect(screen.getByRole('button', { name: 'Review' })).toBeEnabled();
    });

    it('has no accessibility violations and 44 px targets for the buttons on a phone', async () => {
        const { baseElement } = open();
        expect(await axeViolations(baseElement)).toEqual([]);
        for (const button of screen.getAllByRole('button')) expect(button.className).toMatch(/min-h-\[44px\]|h-11/);
    });
});

describe('step 2, review', () => {
    it('shows what is not copied with counts, what was adjusted and the restriction, for a new form', async () => {
        open();
        await goToReview();
        expect(screen.getByText('Step 2 of 3')).toBeInTheDocument();
        expect(served.previewCalls[0]).toEqual({ workspaceId: 'ws-src', formId: 'f-src', targetWorkspaceId: 'ws-prod', targetFormId: null, copyDataProtection: false });
        expect(screen.getByText('A new draft will be made in Voorbeeld Productie.')).toBeInTheDocument();
        expect(screen.getByText('The copy has 2 pages and 7 questions.')).toBeInTheDocument();
        expect(screen.getByText('The copy will not be restricted.')).toBeInTheDocument();
        expect(screen.getByText('Nothing to compare: this will be a new form.')).toBeInTheDocument();
        expect(screen.getByText('Answers are never copied.')).toBeInTheDocument();
        expect(screen.getByText('Not copied: 2 webhooks, 1 email message, 1 case system hand-over. Set them up in the new workspace.')).toBeInTheDocument();
        expect(screen.getByText(/Who can open the form, its link, its dates/)).toBeInTheDocument();
        expect(screen.getByText('3 images could not be copied because they are not stored here. Add them again.')).toBeInTheDocument();
        expect(screen.getByText('2 answer lists were matched by name.')).toBeInTheDocument();
        // no data protection choice for a new form: it takes the source's
        expect(screen.queryByLabelText(/Also copy the data protection settings/)).toBeNull();
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeEnabled();
    });

    it('says the copy will be restricted when it is', async () => {
        served.preview = () => Promise.resolve(goodPreview({ copyIsRestricted: true }));
        open();
        await goToReview();
        expect(screen.getByText(/The copy will be restricted\. Only owners, admins and its creator/)).toBeInTheDocument();
    });

    it('words the diff of an existing target with the versions-compare sentences', async () => {
        served.preview = () => Promise.resolve(existingPreview());
        open();
        await goToReview(true);
        expect(served.previewCalls[0]).toMatchObject({ targetFormId: 'f-old', copyDataProtection: false });
        expect(screen.getByText('The draft of Zorgvuldig formulier in Voorbeeld Productie will be replaced.')).toBeInTheDocument();
        const changes = screen.getByRole('region', { name: 'What will change' });
        expect(within(changes).getByText(/Aanmelding vrijwilligers/)).toBeInTheDocument();
        expect(within(changes).getByText(/Telefoonnummer/)).toBeInTheDocument();
        expect(screen.getByText('This form keeps how long it stores answers.')).toBeInTheDocument();
    });

    it('lists every validation error with where it is and keeps Copy off', async () => {
        served.preview = () =>
            Promise.resolve(
                goodPreview({
                    valid: false,
                    errors: [
                        { path: '/pages/1/fields/2/validations/pattern', code: 'bad_pattern', message: 'The pattern cannot be used.' },
                        { path: '/title', message: 'The form needs a title.' }
                    ],
                    warnings: [{ path: '/pages/0', message: 'A page without questions.' }]
                })
            );
        open();
        await goToReview();
        const alert = screen.getByTestId('promotion-errors');
        expect(alert).toHaveAttribute('role', 'alert');
        expect(within(alert).getByText('Page 2, question 3:')).toBeInTheDocument();
        expect(within(alert).getByText(/The pattern cannot be used\./)).toBeInTheDocument();
        expect(within(alert).getByText('The form needs a title.')).toBeInTheDocument();
        expect(screen.getByText(/A page without questions\./)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeDisabled();
    });

    it('has no accessibility violations', async () => {
        served.preview = () => Promise.resolve(existingPreview({ retentionShortened: true, targetChangedSinceLastPromotion: true }));
        const { baseElement } = open();
        await goToReview(true);
        fireEvent.click(screen.getByLabelText(/Also copy the data protection settings/));
        await screen.findByTestId('promotion-retention-warning');
        expect(await axeViolations(baseElement)).toEqual([]);
    });
});

describe('the restriction, the overwrite and the retention', () => {
    it('refuses a restricted copy onto an open form: "Restrict the target form first", linking to that form’s Access page', async () => {
        served.preview = () => Promise.resolve(existingPreview({ valid: false, errors: [{ path: '/targetFormId', code: 'target_not_restricted', message: 'Restrict the target form first' }] }));
        open();
        await goToReview(true);
        const alert = screen.getByTestId('promotion-error-target_not_restricted');
        expect(alert).toHaveAttribute('role', 'alert');
        expect(within(alert).getByText('Restrict the target form first')).toBeInTheDocument();
        const link = within(alert).getByRole('link', { name: /Open the access settings of that form/ });
        expect(link).toHaveAttribute('href', '/voorbeeld-productie/dashboard/forms/f-old/settings/access');
        expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeDisabled();
        // after restricting it there, the review is run again
        served.preview = () => Promise.resolve(existingPreview({ copyIsRestricted: true }));
        fireEvent.click(within(alert).getByRole('button', { name: 'Review again' }));
        await waitFor(() => expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeEnabled());
        expect(screen.queryByTestId('promotion-error-target_not_restricted')).toBeNull();
    });

    it('needs the overwrite tick when the target changed since the last copy', async () => {
        served.preview = () => Promise.resolve(existingPreview({ targetChangedSinceLastPromotion: true }));
        open();
        await goToReview(true);
        expect(screen.getByText(/This form was changed here since it was last copied/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeDisabled();
        fireEvent.click(screen.getByLabelText('Overwrite the changes made here'));
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
        expect(served.applyCalls[0]).toMatchObject({ overwrite: true, targetEtag: '"t1"', sourceEtag: '"s1"' });
    });

    it('keeps the target’s data protection unless ticked, and asks twice when ticking would shorten the retention', async () => {
        served.preview = (arg) => Promise.resolve(existingPreview({ retentionShortened: arg.copyDataProtection }));
        open();
        await goToReview(true);
        expect(screen.queryByTestId('promotion-retention-warning')).toBeNull();
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeEnabled();

        fireEvent.click(screen.getByLabelText(/Also copy the data protection settings/));
        await waitFor(() => expect(served.previewCalls.at(-1)).toMatchObject({ copyDataProtection: true }));
        const warning = await screen.findByTestId('promotion-retention-warning');
        expect(warning).toHaveAttribute('role', 'alert');
        expect(warning).toHaveTextContent('This shortens how long answers are kept in Zorgvuldig formulier.');
        // the explicit confirmation
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeDisabled();
        fireEvent.click(screen.getByLabelText('I understand that answers may be deleted sooner'));
        expect(screen.getByRole('button', { name: 'Copy as draft' })).toBeEnabled();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
        expect(served.applyCalls[0]).toMatchObject({ copyDataProtection: true, confirmShorterRetention: true });
    });

    it('does not send the confirmation when the data protection settings are not copied', async () => {
        open();
        await goToReview(true);
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
        expect(served.applyCalls[0]).toMatchObject({ copyDataProtection: false, confirmShorterRetention: false, overwrite: false });
    });
});

describe('step 3, done', () => {
    it('links to the new draft and reminds that it is a draft and that automations are set up there', async () => {
        open();
        await goToReview();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const done = await screen.findByTestId('promotion-done');
        expect(screen.getByText('Step 3 of 3')).toBeInTheDocument();
        expect(screen.getByRole('heading', { name: 'Copied as a draft' })).toBeInTheDocument();
        expect(within(done).getByText('The copy is a draft. Publish it in Voorbeeld Productie when it is ready.')).toBeInTheDocument();
        expect(within(done).getByText(/Automations are not copied\. Set up webhooks, email messages and other connections in Voorbeeld Productie before you publish\./)).toBeInTheDocument();
        expect(within(done).getByRole('link', { name: 'Open the copy' })).toHaveAttribute('href', '/voorbeeld-productie/dashboard/forms/f-new');
        // focus moved to the new step's heading
        await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Copied as a draft' })));
        // one key for the copy, a header the server needs
        expect(served.applyCalls[0].idempotencyKey).toMatch(/^[\x20-\x7e]{8,200}$/);
    });

    it('says "Draft updated" for an existing form', async () => {
        served.preview = () => Promise.resolve(existingPreview());
        served.apply = () => Promise.resolve({ formId: 'f-old', workspaceId: 'ws-prod', created: false, adjusted: {} });
        open();
        await goToReview(true);
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        expect(await screen.findByRole('heading', { name: 'Draft updated' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Open the copy' })).toHaveAttribute('href', '/voorbeeld-productie/dashboard/forms/f-old');
    });

    it('has no accessibility violations', async () => {
        const { baseElement } = open();
        await goToReview();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
        expect(await axeViolations(baseElement)).toEqual([]);
    });
});

describe('every error the server can answer', () => {
    const refusals: Array<[string, number, any]> = [
        ['target_not_restricted', 409, { code: 'target_not_restricted', message: 'Restrict the target form first' }],
        ['promotion_from_restricted_form', 403, { code: 'promotion_from_restricted_form', message: 'x' }],
        ['retention_confirmation_required', 422, { code: 'retention_confirmation_required', message: 'x' }],
        ['target_changed', 409, { code: 'target_changed', message: 'x' }],
        ['form_promotion_disabled', 422, { code: 'form_promotion_disabled', message: 'x' }],
        ['form_not_promotable', 422, { code: 'form_not_promotable', message: 'x' }],
        ['same_form', 422, { code: 'same_form', message: 'x' }],
        ['promotion_needs_session', 403, { code: 'promotion_needs_session', message: 'x' }],
        ['rate_limited', 429, { code: 'rate_limited', message: 'x' }],
        ['audit_unavailable', 503, { code: 'audit_unavailable', message: 'x' }],
        ['idempotency_in_progress', 409, { code: 'idempotency_in_progress', message: 'x' }],
        ['not_found', 404, 'Form not found'],
        ['unknown', 500, null]
    ];

    it.each(refusals)('%s is said in a sentence, announced as an alert, in English', async (kind, status, data) => {
        served.apply = () => reject(status, data);
        open();
        await goToReview();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const alert = await screen.findByTestId(kind === 'target_not_restricted' || kind === 'retention_confirmation_required' ? `promotion-error-${kind}` : `promotion-error-${kind}`);
        expect(alert).toHaveAttribute('role', 'alert');
        const sentence = i18n.getFixedT('en')(failureKey(kind as any));
        expect(sentence).not.toBe(failureKey(kind as any));
        expect(alert).toHaveTextContent(sentence.slice(0, 40));
        // the person is still on the review, nothing is claimed as copied
        expect(screen.queryByTestId('promotion-done')).toBeNull();
    });

    it('is said in Dutch too', async () => {
        await i18n.changeLanguage('nl');
        served.apply = () => reject(409, { code: 'target_changed', message: 'x' });
        open();
        fireEvent.click(await screen.findByRole('radio', { name: 'Voorbeeld Productie' }));
        fireEvent.click(screen.getByRole('button', { name: 'Controleren' }));
        await screen.findByRole('heading', { name: 'Controleren' });
        fireEvent.click(screen.getByRole('button', { name: 'Kopiëren als concept' }));
        const alert = await screen.findByTestId('promotion-error-target_changed');
        expect(alert).toHaveTextContent('Het doelformulier is hier gewijzigd sinds het voor het laatst is gekopieerd.');
        expect(within(alert).getByRole('button', { name: 'Opnieuw controleren' })).toBeInTheDocument();
    });

    it('has a sentence in both languages for every kind', () => {
        for (const kind of PROMOTION_FAILURES) {
            const en = i18n.getFixedT('en')(failureKey(kind));
            const nl = i18n.getFixedT('nl')(failureKey(kind));
            expect(en, kind).not.toBe(failureKey(kind));
            expect(nl, kind).not.toBe(failureKey(kind));
            expect(nl, kind).not.toBe(en);
        }
    });

    it('target_changed offers "Review again", which reviews again', async () => {
        served.apply = () => reject(409, { code: 'target_changed', message: 'x' });
        open();
        await goToReview();
        const before = served.previewCalls.length;
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const alert = await screen.findByTestId('promotion-error-target_changed');
        fireEvent.click(within(alert).getByRole('button', { name: 'Review again' }));
        await waitFor(() => expect(served.previewCalls.length).toBe(before + 1));
        // the new review shows the overwrite tick
        expect(screen.queryByTestId('promotion-error-target_changed')).toBeNull();
    });

    it('precondition_failed reviews again by itself and says why', async () => {
        let first = true;
        served.apply = () => {
            if (first) {
                first = false;
                return reject(412, { code: 'precondition_failed', message: 'x' });
            }
            return Promise.resolve({ formId: 'f-new', workspaceId: 'ws-prod', created: true, adjusted: {} });
        };
        let etag = 1;
        served.preview = () => Promise.resolve(goodPreview({ sourceEtag: `"s${etag++}"` }));
        open();
        await goToReview();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const notice = await screen.findByTestId('promotion-notice-precondition_failed');
        expect(notice).toHaveTextContent('One of the forms changed while you were reviewing.');
        expect(served.previewCalls).toHaveLength(2);
        // the second try sends the new review's version, under a new key
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
        expect(served.applyCalls[1].sourceEtag).toBe('"s2"');
        expect(served.applyCalls[1].idempotencyKey).not.toBe(served.applyCalls[0].idempotencyKey);
    });

    it('invalid_spec lists the problems the server found', async () => {
        served.apply = () => reject(422, { code: 'invalid_spec', message: 'x', errors: [{ path: '/pages/0/fields/0', message: 'This question has no title.' }] });
        open();
        await goToReview();
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const errors = await screen.findByTestId('promotion-errors');
        expect(within(errors).getByText('Page 1, question 1:')).toBeInTheDocument();
        expect(within(errors).getByText(/This question has no title\./)).toBeInTheDocument();
        expect(screen.getByTestId('promotion-error-invalid_spec')).toHaveTextContent('The problems are listed above.');
    });

    it('a refusal at apply that the review did not see: restricted target', async () => {
        served.preview = () => Promise.resolve(existingPreview());
        served.apply = () => reject(409, { code: 'target_not_restricted', message: 'Restrict the target form first' });
        open();
        await goToReview(true);
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        const alert = await screen.findByTestId('promotion-error-target_not_restricted');
        expect(within(alert).getByRole('link', { name: /access settings/ })).toHaveAttribute('href', '/voorbeeld-productie/dashboard/forms/f-old/settings/access');
    });

    it('a retention confirmation the review did not ask for is asked at apply', async () => {
        let asked = false;
        served.preview = () => Promise.resolve(existingPreview());
        served.apply = (arg) => {
            if (arg.copyDataProtection && !arg.confirmShorterRetention) {
                asked = true;
                return reject(422, { code: 'retention_confirmation_required', message: 'x' });
            }
            return Promise.resolve({ formId: 'f-old', workspaceId: 'ws-prod', created: false, adjusted: {} });
        };
        open();
        await goToReview(true);
        fireEvent.click(screen.getByLabelText(/Also copy the data protection settings/));
        await waitFor(() => expect(served.previewCalls.length).toBe(2));
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-error-retention_confirmation_required');
        expect(asked).toBe(true);
        // now the confirmation is there to tick
        fireEvent.click(screen.getByLabelText('I understand that answers may be deleted sooner'));
        fireEvent.click(screen.getByRole('button', { name: 'Copy as draft' }));
        await screen.findByTestId('promotion-done');
    });

    it('a failed review is an alert with a way to try again', async () => {
        let calls = 0;
        served.preview = () => (++calls === 1 ? reject(500, null) : Promise.resolve(goodPreview()));
        open();
        fireEvent.click(await screen.findByRole('radio', { name: 'Voorbeeld Productie' }));
        fireEvent.click(screen.getByRole('button', { name: 'Review' }));
        const alert = await screen.findByTestId('promotion-error-unknown');
        fireEvent.click(within(alert).getByRole('button', { name: 'Review again' }));
        await screen.findByText('A new draft will be made in Voorbeeld Productie.');
    });
});

describe('the answer to a refusal', () => {
    it('is chosen by the code of the body, then the status', () => {
        expect(failureOf({ status: 409, data: { code: 'target_changed' } }).kind).toBe('target_changed');
        expect(failureOf({ status: 412, data: { code: 'precondition_failed' } }).kind).toBe('precondition_failed');
        expect(failureOf({ status: 412, data: null }).kind).toBe('precondition_failed');
        expect(failureOf({ status: 404, data: 'Form not found' }).kind).toBe('not_found');
        expect(failureOf({ status: 429, data: {} }).kind).toBe('rate_limited');
        expect(failureOf({ status: 418, data: { code: 'something_new' } }).kind).toBe('unknown');
        expect(failureOf(undefined).kind).toBe('unknown');
        expect(failureOf({ status: 422, data: { code: 'invalid_spec', errors: [{ message: 'a' }, 7, null] } }).problems).toEqual([{ message: 'a' }]);
    });

    it('turns a JSON pointer into page and question numbers', () => {
        expect(whereOf('/pages/0/fields/4/title')).toEqual({ page: 1, question: 5 });
        expect(whereOf('/pages/2')).toEqual({ page: 3, question: undefined });
        expect(whereOf('/title')).toBeNull();
        expect(whereOf(undefined)).toBeNull();
    });
});

describe('closing', () => {
    it('Escape closes it and nothing is sent', async () => {
        open();
        const dialog = screen.getByRole('dialog');
        await act(async () => {
            fireEvent.keyDown(dialog, { key: 'Escape' });
        });
        expect(closed).toHaveBeenCalledWith(false);
        expect(served.applyCalls).toEqual([]);
    });

    it('renders nothing, and asks nothing, while closed', () => {
        render(<FormPromotionDialog open={false} onOpenChange={() => {}} workspace={workspace} form={form} />);
        expect(screen.queryByRole('dialog')).toBeNull();
        expect(served.targetsCalls).toEqual([]);
        expect(served.previewCalls).toEqual([]);
    });
});
