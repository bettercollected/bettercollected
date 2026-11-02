import { pathSegment, workspacesApi } from '@app/store/workspaces/api';
import type { VersionChange } from '@app/store/workspaces/form-versions-api';
import { fileNameFromDisposition } from '@app/utils/content-disposition';

// Copying a form to another workspace (backend controllers/form_promotion_router.py). All four routes answer 422
// `form_promotion_disabled` while the server's FORM_PROMOTION_ENABLED is off; the webapp asks for none of them then
// (`useWorkspacePermissions().formPromotionEnabled`). The server decides every rule, on both sides; nothing here is trusted.

export interface PromotionRequest {
    targetWorkspaceId: string;
    /** None: a new form; else the form of the target workspace whose draft is replaced. */
    targetFormId?: string | null;
    copyDataProtection?: boolean;
    sourceEtag?: string | null;
    targetEtag?: string | null;
}

export interface ApplyPromotionRequest extends PromotionRequest {
    sourceEtag: string;
    overwrite?: boolean;
    confirmShorterRetention?: boolean;
}

/** One problem the target's checks found: where (a JSON pointer into the form file), a code when there is one, and the server's message. */
export interface PromotionProblem {
    path?: string | null;
    code?: string | null;
    message: string;
}

export interface PromotionAdjusted {
    /** Only the kinds that happened. */
    counts: Record<string, number>;
    patternsDropped: string[];
    listsMatchedByName: string[];
    listsNotFound: string[];
    answerSourcesDropped: string[];
    shareAsChoicesOff: string[];
    trustKept: string[];
}

export interface PromotionDiff {
    changed: boolean;
    entries: VersionChange[];
    truncated: boolean;
}

export interface PromotionPreview {
    valid: boolean;
    errors: PromotionProblem[];
    warnings: PromotionProblem[];
    created: boolean;
    /** What the target's draft changes into (an existing target only). */
    diff?: PromotionDiff | null;
    counts: { pages: number; questions: number };
    /** Counts of what is not copied; null for someone who may only read the form. */
    notCarried?: Record<string, number> | null;
    alsoNotCopied: string[];
    adjusted: PromotionAdjusted;
    /** What the target will be: a new form takes its source's mode, an existing one keeps its own. */
    copyIsRestricted: boolean;
    sourceEtag: string;
    targetEtag?: string | null;
    targetChangedSinceLastPromotion: boolean;
    retentionShortened: boolean;
}

export interface PromotionTarget {
    formId: string;
    title?: string | null;
    copiedFromSource: boolean;
    published?: boolean | null;
}

export interface PromotionTargets {
    items: PromotionTarget[];
    more: boolean;
}

export interface PromotionApplied {
    formId: string;
    workspaceId: string;
    created: boolean;
    etag?: string | null;
    notCarried?: Record<string, number> | null;
    adjusted: Record<string, number>;
}

export interface FormFile {
    blob: Blob;
    fileName: string;
}

const FALLBACK_FILE_NAME = 'form.json';

/** The refusal's body when there is one (`{code, message, ...}`), whatever the content type said. */
async function refusalOf(response: Response): Promise<any> {
    try {
        return await response.json();
    } catch {
        return null;
    }
}

export const formPromotionApi = workspacesApi.injectEndpoints({
    endpoints: (builder) => ({
        getPromotionTargets: builder.query<PromotionTargets, { workspaceId: string; formId: string; targetWorkspaceId: string; q?: string }>({
            query: ({ workspaceId, formId, targetWorkspaceId, q }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/promotion/targets`,
                method: 'GET',
                params: { targetWorkspaceId, ...(q ? { q } : {}) }
            }),
            // another workspace's form titles: not kept once nobody shows them
            keepUnusedDataFor: 0
        }),
        previewPromotion: builder.mutation<PromotionPreview, { workspaceId: string; formId: string } & PromotionRequest>({
            query: ({ workspaceId, formId, ...body }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/promotion/preview`,
                method: 'POST',
                body
            })
        }),
        applyPromotion: builder.mutation<PromotionApplied, { workspaceId: string; formId: string; idempotencyKey: string } & ApplyPromotionRequest>({
            query: ({ workspaceId, formId, idempotencyKey, ...body }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/promotion/apply`,
                method: 'POST',
                body,
                headers: { 'Idempotency-Key': idempotencyKey }
            })
        }),
        // The form's document as a file (it holds no answer): `no-store`, audited by the server.
        downloadFormFile: builder.mutation<FormFile, { workspaceId: string; formId: string }>({
            query: ({ workspaceId, formId }) => ({
                url: `/workspaces/${pathSegment(workspaceId)}/forms/${pathSegment(formId)}/spec-file`,
                method: 'GET',
                responseHandler: async (response: Response) => {
                    if (!response.ok) return refusalOf(response);
                    return { blob: await response.blob(), fileName: fileNameFromDisposition(response.headers.get('Content-Disposition')) ?? FALLBACK_FILE_NAME };
                }
            })
        })
    })
});

export const { useGetPromotionTargetsQuery, usePreviewPromotionMutation, useApplyPromotionMutation, useDownloadFormFileMutation } = formPromotionApi;

/** Save the form file through a temporary link (the way the other downloads do). */
export function saveFormFile({ blob, fileName }: FormFile): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName.endsWith('.json') ? fileName : `${fileName}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
