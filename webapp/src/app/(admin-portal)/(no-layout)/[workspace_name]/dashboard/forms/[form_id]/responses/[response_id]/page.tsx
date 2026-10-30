import ResponsePage from '@app/components/response-page/response-page';

// Never the respondent's email or answers: the tab title lands in browser history.
// (The page sets "Response · <form title>" once the form is known.)
export const metadata = { title: { absolute: 'Response' }, robots: { index: false, follow: false } };

export default async function Page({ params }: { params: Promise<{ form_id: string; response_id: string }> }) {
    const { form_id, response_id } = await params;
    return <ResponsePage formId={form_id} responseId={response_id} />;
}
