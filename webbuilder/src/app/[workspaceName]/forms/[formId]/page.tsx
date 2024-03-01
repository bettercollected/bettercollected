export default function ({
    params
}: {
    params: { formId: string; workspaceName: string };
}) {
    const { formId, workspaceName } = params;
    console.log(formId, workspaceName);
    return <div></div>;
}
