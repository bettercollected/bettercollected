// Kept apart from utils/response-page.ts, which pulls in the form builder's code:
// server components (the redirect of the form page) need only these two.

/** Where staff read one response (the id only: never the receipt number, an email or an answer). */
export const responsePageUrl = (workspaceName: string, formId: string, responseId: string) => `/${workspaceName}/dashboard/forms/${formId}/responses/${encodeURIComponent(responseId)}`;

/** The responses list of a form. */
export const responsesListUrl = (workspaceName: string, formId: string) => `/${workspaceName}/dashboard/forms/${formId}/responses`;
