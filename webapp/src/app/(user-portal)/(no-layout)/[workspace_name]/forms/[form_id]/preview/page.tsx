'use client';

import { setForm } from "@app/store/forms/slice";
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from "@app/store/jotai/form";
import { useGetWorkspaceFormQuery } from "@app/store/workspaces/api";
import { selectWorkspace } from '@app/store/workspaces/slice';
import FullScreenLoader from "@app/views/atoms/full-screen-loader";
import TrustLayer from '@app/views/molecules/form/trust-layer';
import Form from "@app/views/organism/form/form";
import { layoutOfPage } from '@app/views/organism/layout/form-column';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { use, useEffect } from "react";

export default function FormPreview(props: { params: Promise<{ form_id: string }> }) {
    const params = use(props.params);

    const dispatch = useAppDispatch();
    const { updateFormTheme } = useFormState();

    const workspace = useAppSelector(selectWorkspace);
    const { currentSlide, endingId } = useResponderState();
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
            data.theme && updateFormTheme(data.theme, { undoable: false });
        }
    }, [data]);

    if (!data?.formId) {
        return <FullScreenLoader />
    }
    // Preview shows exactly what responders will see, trust strip included,
    // laid out as on the live form page (form above, strip below, in flow).
    return <div className="relative flex h-dvh w-screen flex-col">
        <div className="relative min-h-0 flex-1">
            <Form isPreviewMode />
        </div>
        <div className="relative z-40 shrink-0">
            <TrustLayer ownerName={workspace?.title || workspace?.workspaceName} ownerImage={workspace?.profileImage} settings={data?.settings} registrationDestination={data?.registrationDestination} layout={layoutOfPage(data, currentSlide, endingId)} />
        </div>
    </div>
}
