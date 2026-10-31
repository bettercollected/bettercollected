import { formsApi } from '@app/store/redux/form-api';

// Save and continue later (backend services/form_drafts). Respondent routes:
// the signed-in respondent is known by the session, an anonymous one by the
// edit key or the link's token in the body, never in a URL or a header.
// Every body is sent as JSON and every answer is the respondent's own text.

export interface DraftContent {
    answers: Record<string, any>;
    hiddenFields: Record<string, string>;
    position?: { pageId?: string | null; history: string[] } | null;
}

export interface SaveDraftBody extends DraftContent {
    /** The key of the browser that made an anonymous draft (never the link's token). */
    editKey?: string;
    /** The published version the answers were given against. */
    formVersion?: number;
}

export interface LinkDraftBody extends SaveDraftBody {
    email: string;
    locale?: string;
}

export interface DraftSaved {
    savedAt: string;
    expiresAt: string;
}

export interface DraftLinkSent extends DraftSaved {
    editKey: string;
}

export interface OpenedDraft extends DraftContent {
    savedAt: string;
    expiresAt: string;
    formVersion?: number | null;
    currentVersion?: number | null;
    formChanged: boolean;
    /** Only for an anonymous draft opened with its link. */
    editKey?: string;
}

/** The form takes no responses now: no answers come back. */
export interface UnavailableDraft {
    unavailable: 'closed' | 'not_yet_open' | 'full';
    expiresAt: string;
}

export const isUnavailableDraft = (draft: OpenedDraft | UnavailableDraft): draft is UnavailableDraft => 'unavailable' in draft;

type FormKey = { workspaceId: string; formId: string };

const url = ({ workspaceId, formId }: FormKey, tail = '') => `/workspaces/${workspaceId}/forms/${formId}/drafts${tail}`;

export const draftsApi = formsApi.injectEndpoints({
    endpoints: (builder) => ({
        saveDraft: builder.mutation<DraftSaved, FormKey & { body: SaveDraftBody }>({
            query: ({ body, ...key }) => ({ url: url(key), method: 'PUT', body })
        }),
        requestDraftLink: builder.mutation<DraftLinkSent, FormKey & { body: LinkDraftBody }>({
            query: ({ body, ...key }) => ({ url: url(key, '/link'), method: 'POST', body })
        }),
        // POST, not GET: the token travels in the body.
        openDraft: builder.mutation<OpenedDraft | UnavailableDraft, FormKey & { token: string }>({
            query: ({ token, ...key }) => ({ url: url(key, '/open'), method: 'POST', body: { token } })
        }),
        getMyDraft: builder.mutation<OpenedDraft | UnavailableDraft, FormKey>({
            query: (key) => ({ url: url(key, '/mine'), method: 'POST' })
        }),
        discardDraft: builder.mutation<{ deleted: boolean }, FormKey & { editKey?: string; token?: string }>({
            query: ({ editKey, token, ...key }) => ({ url: url(key, '/discard'), method: 'POST', body: { editKey, token } })
        })
    })
});

export const { useSaveDraftMutation, useRequestDraftLinkMutation, useOpenDraftMutation, useGetMyDraftMutation, useDiscardDraftMutation } = draftsApi;
