export default function FormPage({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const { formId, workspaceName } = params;
    console.log('forms', formId, workspaceName);
    return <div></div>;
}
