'use client';

import { setForm } from "@app/store/forms/slice";
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from "@app/store/jotai/form";
import { useGetWorkspaceFormQuery } from "@app/store/workspaces/api";
import { selectWorkspace } from '@app/store/workspaces/slice';
import FullScreenLoader from "@app/views/atoms/full-screen-loader";
import TrustLayer from '@app/views/molecules/form/trust-layer';
import Form from "@app/views/organism/form/form";
import { use, useEffect } from "react";

export default function FormPreview(props: { params: Promise<{ form_id: string }> }) {
    const params = use(props.params);

    const dispatch = useAppDispatch();
    const { updateFormTheme } = useFormState();

    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: params.form_id,
        },
        { skip: !workspace.id }
    );


    useEffect(() => {
        if (data?.formId) {
            dispatch(setForm(data));
            data.theme && updateFormTheme(data.theme);
        }
    }, [data]);

    if (!data?.formId) {
        return <FullScreenLoader />
    }
    return <div className="relative h-screen w-screen">
        <Form isPreviewMode />
        {/* Preview shows exactly what responders will see, trust strip included. */}
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40">
            <TrustLayer ownerName={workspace?.title || workspace?.workspaceName} ownerImage={workspace?.profileImage} purpose={data?.settings?.purpose} retention={data?.settings?.retentionText} privacyUrl={data?.settings?.privacyPolicyUrl} poweredBy={!data?.settings?.disableBranding} />
        </div>
    </div>
}
