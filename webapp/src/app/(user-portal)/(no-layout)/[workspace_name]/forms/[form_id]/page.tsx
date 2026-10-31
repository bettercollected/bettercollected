'use client';

import DraftResume from '@app/components/drafts/draft-resume';
import Loader from '@app/components/ui/loader';
import { trackCanonicalFormView } from '@app/lib/analytics/umami';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { selectResponderForm, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useHiddenFieldValues } from '@app/store/jotai/responder-hidden-fields';
import { useResponderState, useShownSlide } from '@app/store/jotai/responder-form-state';
import { useGetWorkspaceFormQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ownerProps } from '@app/utils/workspace-display-name';
import { captureHiddenFieldValues, getPrefillEntries } from '@app/utils/answer-piping';
import { isUnavailableForm } from '@app/utils/closed-form';
import { takeResumeToken } from '@app/utils/form-drafts';
import { httpUrl } from '@app/utils/http-url';
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
        // keyed by the form: another form starts with its own state (and its own link)
        <FetchFormWrapper key={slug} slug={slug} />
    );
}

const FetchFormWrapper = ({ slug }: { slug: string }) => {
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const iframeRef = useRef(null);
    // A draft's link (#resume=<token>): taken from the address bar and history as the page starts,
    // before the form loads, and kept in memory (utils/form-drafts.ts).
    const [resumeToken] = useState(() => takeResumeToken());
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
    const { currentSlide, endingId, resetResponderState } = useResponderState();
    // The form on screen and the page of it shown (a closed form shows its
    // welcome page): the trust strip is laid out for the same page as the form.
    const shownForm = useAppSelector(selectResponderForm);
    const shownSlide = useShownSlide();
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

    // A refetch of the form on screen, not another form: the respondent's
    // place is kept in an app-wide atom, so it outlives a same-tab move from
    // one form to the next.
    const sameForm = !!data?.formId && shownForm?.formId === data.formId;
    // A respondent on an ending keeps it: a refetch (focus, reconnect) that
    // brings the form back closed has no endings, and an ending may pipe their
    // answers into its text. The closed form is shown once they leave it.
    const keepEnding = isUnavailableForm(data) && currentSlide === -2 && sameForm;

    useEffect(() => {
        if (!data?.formId || keepEnding) return;
        // Another form starts at its welcome page, not at the place (or the
        // ending) reached in the previous one.
        if (!sameForm) resetResponderState();
        dispatch(setForm(data));
        data.theme && updateFormTheme(data.theme, { undoable: false });
    }, [data, keepEnding]);

    // The original form is opened or framed only at an http(s) address;
    // without one the form is shown here.
    const originalUrl = httpUrl(data?.settings?.embedUrl);
    const showOriginal = !!(data?.importedFormId && data.settings?.showOriginalForm && originalUrl);

    useEffect(() => {
        if (showOriginal && originalUrl && hasFileUpload(data?.fields || [])) {
            router.push(originalUrl);
        }
    }, [data]);

    if (isLoading || error || (showOriginal && hasFileUpload(data?.fields || []))) {
        return <FullScreenLoader />;
    }

    if (showOriginal) {
        return (
            <>
                <div className="relative min-h-screen!">
                    <div className="m-0!' absolute bottom-0 left-0 right-0 top-0 p-0!">
                        <iframe ref={iframeRef} src={`${originalUrl}?embedded=true`} width="100%" height="100%">
                            <Loader />
                        </iframe>
                    </div>
                </div>
            </>
        );
    }

    // A closed form is served without its questions or its imported id,
    // whichever builder made it: it shows the closed notice, never the
    // original.
    if (data?.builderVersion !== 'v2' && !isUnavailableForm(data)) return <div className="relative flex h-dvh w-screen flex-col" />;

    return (
        // The form above, the trust strip (and its panel) below, in flow: the
        // page is centred in the space the strip leaves, and an open panel
        // never covers the form's button. dvh keeps the strip on screen under
        // a phone's browser bars.
        <RespondentPageShell
            // A saved draft, picked up from the link or the account (components/drafts).
            notice={<DraftResume form={data} token={resumeToken} />}
            footer={
                <TrustLayer
                    {...ownerProps(workspace)}
                    ownerImage={workspace?.profileImage}
                    settings={data?.settings}
                    registrationDestination={data?.registrationDestination}
                    webhookDestination={data?.webhookDestination}
                    portalUrl={typeof window !== 'undefined' && window.PUBLIC_CONFIG ? `${window.PUBLIC_CONFIG.HTTP_SCHEME}${window.PUBLIC_CONFIG.FORM_DOMAIN}/${workspace?.workspaceName}` : undefined}
                    layout={layoutOfPage(shownForm, shownSlide, endingId)}
                    // Open on the welcome page when the screen has room for
                    // both; a strip with the toggle elsewhere, and on phones,
                    // where the open panel would take half the screen.
                    defaultExpanded={shownSlide === -1 && roomy}
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
