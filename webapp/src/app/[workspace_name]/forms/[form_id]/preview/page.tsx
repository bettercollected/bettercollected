'use client';

import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';
import {useGetWorkspaceFormQuery} from "@app/store/workspaces/api";
import Form from "@app/views/organism/Form/Form";
import FullScreenLoader from "@app/views/atoms/Loaders/FullScreenLoader";
import {useEffect} from "react";
import {setForm} from "@app/store/forms/slice";
import {useFormState} from "@app/store/jotai/form";

export default function FormPreview({params}: { params: { form_id: string } }) {

    const dispatch = useAppDispatch();
    const {updateFormTheme} = useFormState();

    const workspace = useAppSelector(selectWorkspace);
    const {data} = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: params.form_id,
        },
        {skip: !workspace.id}
    );


    useEffect(() => {
        if (data?.formId) {
            dispatch(setForm(data));
            data.theme && updateFormTheme(data.theme);
        }
    }, [data]);

    if (!data?.formId) {
        return <FullScreenLoader/>
    }
    return <div className="h-screen w-screen">
        <Form isPreviewMode/>
    </div>

}
