import ResponsePage from '@app/components/response-page/response-page';
import { responseOrigin } from '@app/utils/response-urls';

// Never the respondent's email or answers: the tab title lands in browser history.
// (The page sets "Response · <form title>" once the form is known.)
export const metadata = { title: { absolute: 'Response' }, robots: { index: false, follow: false } };

export default async function Page({ params, searchParams }: { params: Promise<{ form_id: string; response_id: string }>; searchParams: Promise<{ from?: string | string[] }> }) {
    const { form_id, response_id } = await params;
    // `?from=` names the list the page was opened from; only the fixed names count (never an address)
    const { from } = await searchParams;
    return <ResponsePage formId={form_id} responseId={response_id} origin={responseOrigin(from)} />;
}
