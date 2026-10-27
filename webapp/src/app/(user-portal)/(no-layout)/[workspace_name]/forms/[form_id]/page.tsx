'use client';

import Loader from '@app/components/ui/loader';
import { trackCanonicalFormView } from '@app/lib/analytics/umami';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { captureHiddenFieldValues, getPrefillEntries } from '@app/utils/answer-piping';
import FullScreenLoader from '@app/views/atoms/full-screen-loader';
import Form from '@app/views/organism/form/form';
import RespondentPageShell from '@app/views/organism/form/respondent-page-shell';
import TrustLayer from '@app/views/molecules/form/trust-layer';
import { layoutOfPage } from '@app/views/organism/layout/form-column';
import { useRouter } from 'next/navigation';
import { use, useEffect, useRef, useState } from 'react';

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
    const { currentSlide, endingId } = useResponderState();
    const roomy = useMinViewportSize(640);

    useEffect(() => {
        if (trackedViewRef.current) return;
        if (!workspace?.workspaceName || !data?.formId) return;
        trackedViewRef.current = true;
        trackCanonicalFormView(workspace.workspaceName, slug);
    }, [workspace?.workspaceName, data?.formId, slug]);

    const { setHiddenValues } = useHiddenFieldValues();
    const { addFieldTextAnswer, addFieldEmailAnswer, addFieldNumberAnswer, addFieldURLAnswer, addFieldPhoneNumberAnswer, addFieldDateAnswer } = useFormResponse();
    const capturedParamsRef = useRef(false);

    // Once the form definition is in: capture the declared hidden-field values
    // from the share link and apply any `?field_<id>=` prefills. window.location
    // (not useSearchParams) so this stays out of the server render entirely.
    useEffect(() => {
        if (capturedParamsRef.current || !data?.formId) return;
        capturedParamsRef.current = true;

        const search = window.location.search;
        if (!search) return;

        const captured = captureHiddenFieldValues(data.hiddenFields, search);
        if (Object.keys(captured).length) setHiddenValues(captured);

        getPrefillEntries(data.fields, search).forEach(({ field, value }) => {
            switch (field.type) {
                case FieldTypes.SHORT_TEXT:
                case FieldTypes.LONG_TEXT:
                    addFieldTextAnswer(field.id, value);
                    break;
                case FieldTypes.EMAIL:
                    addFieldEmailAnswer(field.id, value);
                    break;
                case FieldTypes.NUMBER:
                    if (Number.isFinite(Number(value))) addFieldNumberAnswer(field.id, Number(value));
                    break;
                case FieldTypes.LINK:
                    addFieldURLAnswer(field.id, value);
                    break;
                case FieldTypes.PHONE_NUMBER:
                    addFieldPhoneNumberAnswer(field.id, value);
                    break;
                case FieldTypes.DATE:
                    addFieldDateAnswer(field.id, value);
                    break;
                default:
                    // Choice/rating/matrix prefill needs option matching — not
                    // supported in this first pass.
                    break;
            }
        });
    }, [data?.formId]);

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
            data.theme && updateFormTheme(data.theme, { undoable: false });
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
                <div className="relative min-h-screen!">
                    <div className="m-0!' absolute bottom-0 left-0 right-0 top-0 p-0!">
                        <iframe ref={iframeRef} src={`${data?.settings?.embedUrl}?embedded=true`} width="100%" height="100%">
                            <Loader />
                        </iframe>
                    </div>
                </div>
            </>
        );
    }

    if (data?.builderVersion !== 'v2') return <div className="relative flex h-dvh w-screen flex-col" />;

    return (
        // The form above, the trust strip (and its panel) below, in flow: the
        // page is centred in the space the strip leaves, and an open panel
        // never covers the form's button. dvh keeps the strip on screen under
        // a phone's browser bars.
        <RespondentPageShell
            footer={
                <TrustLayer
                    ownerName={workspace?.title || workspace?.workspaceName}
                    ownerImage={workspace?.profileImage}
                    settings={data?.settings}
                    registrationDestination={data?.registrationDestination}
                    portalUrl={typeof window !== 'undefined' && window.PUBLIC_CONFIG ? `${window.PUBLIC_CONFIG.HTTP_SCHEME}${window.PUBLIC_CONFIG.FORM_DOMAIN}/${workspace?.workspaceName}` : undefined}
                    layout={layoutOfPage(data, currentSlide, endingId)}
                    // Open on the welcome page when the screen has room for
                    // both; a strip with the toggle elsewhere, and on phones,
                    // where the open panel would take half the screen.
                    defaultExpanded={currentSlide === -1 && roomy}
                    // ...and only when Start stays in view with it open.
                    protectPrimaryAction
                />
            }
        >
            <Form />
        </RespondentPageShell>
    );
};

/** Whether the viewport is at least `px` tall and wide (false on the server). */
function useMinViewportSize(px: number) {
    const [matches, setMatches] = useState(false);
    useEffect(() => {
        const query = window.matchMedia(`(min-height: ${px}px) and (min-width: ${px}px)`);
        const update = () => setMatches(query.matches);
        update();
        query.addEventListener?.('change', update);
        return () => query.removeEventListener?.('change', update);
    }, [px]);
    return matches;
}
