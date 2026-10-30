// Kept apart from utils/response-page.ts, which pulls in the form builder's code:
// server components (the redirect of the form page, the response route) need only these.

/** Where staff read one response (the id only: never the receipt number, an email or an answer). */
export const responsePageUrl = (workspaceName: string, formId: string, responseId: string, origin?: ResponseOrigin) =>
    `/${workspaceName}/dashboard/forms/${formId}/responses/${encodeURIComponent(responseId)}${origin ? `?from=${origin}` : ''}`;

/** The responses list of a form. */
export const responsesListUrl = (workspaceName: string, formId: string) => `/${workspaceName}/dashboard/forms/${formId}/responses`;

/**
 * The lists other than a form's responses that open a response's page: the
 * workspace's deletion requests and a form's. The page goes back (and, after
 * a delete, returns) to the list it came from. Only these fixed names travel
 * in the URL (`?from=`), never an address: each maps to a path built here.
 */
export const RESPONSE_ORIGINS = ['deletion-requests', 'form-deletion-requests'] as const;
export type ResponseOrigin = (typeof RESPONSE_ORIGINS)[number];

/** The origin a `?from=` value names, or undefined for anything else. */
export function responseOrigin(value: unknown): ResponseOrigin | undefined {
    return RESPONSE_ORIGINS.find((origin) => origin === value);
}

/** The list a response's page goes back to: the one it was opened from, else the form's responses. */
export function responseOriginListUrl(workspaceName: string, formId: string, origin?: ResponseOrigin): string {
    if (origin === 'deletion-requests') return `/${workspaceName}/dashboard/deletion-requests`;
    if (origin === 'form-deletion-requests') return `/${workspaceName}/dashboard/forms/${formId}/deletion-requests`;
    return responsesListUrl(workspaceName, formId);
}

/**
 * The tab title of a response's page: "Response · <form title>" for the
 * form the URL names, else plain "Response" (an error body, another form, a
 * failed read). What the page is, never who answered: it lands in browser history.
 */
export function responsePageTitle(form: unknown, formId: string): string {
    const known = !!form && typeof form === 'object' && (form as { formId?: unknown }).formId === formId;
    if (!known) return 'Response';
    const title = (form as { title?: unknown }).title;
    return `Response · ${(typeof title === 'string' && title.trim()) || 'Untitled form'}`;
}
