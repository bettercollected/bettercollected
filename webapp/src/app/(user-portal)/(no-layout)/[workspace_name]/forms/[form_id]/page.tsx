'use client';

import Loader from '@app/components/ui/loader';
import { trackCanonicalFormView } from '@app/lib/analytics/umami';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import Form from '@app/views/organism/form/form';
import TrustLayer from '@app/views/molecules/form/trust-layer';
import { useRouter } from 'next/navigation';
import { use, useEffect, useRef } from 'react';

export default function FormPage(props: { params: Promise<{ form_id: string; workspace_name: string }> }) {
    const params = use(props.params);
    const slug = params.form_id;

    return (
        <FetchFormWrapper slug={slug} />
    );
}

const FetchFormWrapper = ({ slug }: { slug: string }) => {
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const iframeRef = useRef(null);
    const { updateFormTheme } = useFormState();

    const { data, isLoading, error } = useGetWorkspaceFormQuery(
        {
            workspace_id: workspace.id,
            custom_url: slug,
            published: true
        },
        { skip: !workspace.id }
    );

    const router = useRouter();
    const trackedViewRef = useRef(false);

    useEffect(() => {
        if (trackedViewRef.current) return;
        if (!workspace?.workspaceName || !data?.formId) return;
        trackedViewRef.current = true;
        trackCanonicalFormView(workspace.workspaceName, slug);
    }, [workspace?.workspaceName, data?.formId, slug]);

    const hasFileUpload = (fields: Array<any>) => {
        let isUploadField = false;
        if (fields && Array.isArray(fields) && fields.length > 0) {
            fields.forEach((field: StandardFormFieldDto) => {
                if (field.type === FieldTypes.SLIDE) {
                    field?.properties?.fields?.forEach((field: StandardFormFieldDto) => {
                        if (field && field?.type && field.type === FieldTypes.FILE_UPLOAD) {
                            isUploadField = true;
                        }
                    });
                }
                if (field && field?.type && field.type === FieldTypes.FILE_UPLOAD) {
                    isUploadField = true;
                }
            });
            return isUploadField;
        }
        return isUploadField;
    };

    useEffect(() => {
        if (data?.formId) {
            dispatch(setForm(data));
            data.theme && updateFormTheme(data.theme);
        }
    }, [data]);

    useEffect(() => {
        if (data?.importedFormId && data.settings?.showOriginalForm && hasFileUpload(data?.fields || [])) {
            router.push(data?.settings?.embedUrl || '');
        }
    }, [data]);

    if (isLoading || error || (data?.importedFormId && data.settings?.showOriginalForm && hasFileUpload(data?.fields || []))) {
        return <FullScreenLoader />;
    }

    if (data?.importedFormId && data.settings?.showOriginalForm) {
        return (
            <>
                <div className="relative !min-h-screen">
                    <div className="!m-0' absolute bottom-0 left-0 right-0 top-0 !p-0">
                        <iframe ref={iframeRef} src={`${data?.settings?.embedUrl}?embedded=true`} width="100%" height="100%">
                            <Loader />
                        </iframe>
                    </div>
                </div>
            </>
        );
    }

    return (
        <div className="relative h-screen w-screen">
            {data?.builderVersion === 'v2' && <Form />}
            {data?.builderVersion === 'v2' && (
                <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40">
                    <TrustLayer
                        ownerName={workspace?.title || workspace?.workspaceName}
                        ownerImage={workspace?.profileImage}
                        privacyUrl={data?.settings?.privacyPolicyUrl}
                    />
                </div>
            )}
        </div>
    );
};
