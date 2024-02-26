import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import LoggedOutAccountIcon from '@Components/Common/Icons/Common/LoggedOutAccountIcon';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import MarkdownText from '@Components/Common/Markdown';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import CheckboxField from '@Components/Form/CheckboxField';
import DropdownField from '@Components/Form/DropdownField';
import FieldValidations from '@Components/Form/FieldValidations';
import FileUpload from '@Components/Form/FileUpload';
import LayoutFields from '@Components/Form/LayoutFields';
import LongText from '@Components/Form/LongText';
import MultipleChoiceField from '@Components/Form/MultipleChoiceField';
import PhoneNumber from '@Components/Form/PhoneNumber';
import RankingField from '@Components/Form/RankingField';
import RatingField from '@Components/Form/RatingField';
import ShortText from '@Components/Form/ShortText';
import ThankYouPage from '@Components/Form/ThankYouPage';
import { toast } from 'react-toastify';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { Close } from '@app/components/icons/close';
import { Logout } from '@app/components/icons/logout-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { useLogoutMutation } from '@app/store/auth/api';
import { selectAuth } from '@app/store/auth/slice';
import { ConsentAnswerDto } from '@app/store/consent/types';
import { resetFillForm, selectAnswers, selectFormResponderOwnerField, selectInvalidFields, setDataResponseOwnerField, setFillFormId, setInvalidFields } from '@app/store/fill-form/slice';
import { FormValidationError } from '@app/store/fill-form/type';
import { Condition } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useSubmitResponseMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getFullNameFromUser } from '@app/utils/userUtils';
import { validateConditionsAndReturnUpdatedForm, validateFormFieldAnswer } from '@app/utils/validationUtils';

import useFormAtom from './atom';

export interface FormFieldProps {
    field: StandardFormFieldDto;
    ans?: any;
    enabled?: boolean;
}

const renderFormField = (field: StandardFormFieldDto, enabled?: boolean, answer?: any, fields?: Array<StandardFormFieldDto>) => {
    switch (field?.type) {
        case FormBuilderTagNames.LAYOUT_SHORT_TEXT:
        case FormBuilderTagNames.LAYOUT_HEADER3:
        case FormBuilderTagNames.LAYOUT_HEADER1:
        case FormBuilderTagNames.LAYOUT_HEADER4:
        case FormBuilderTagNames.LAYOUT_HEADER2:
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <LayoutFields field={field} enabled={!!enabled} fields={fields} />;
        case FormBuilderTagNames.LAYOUT_MARKDOWN:
            return <MarkdownText text={field.value ?? ''} />;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_LINK:
            return <ShortText enabled={enabled} field={field} ans={answer} />;
        case FormBuilderTagNames.INPUT_DATE:
            return <ShortText enabled={enabled} field={field} ans={answer} helperText={field?.properties?.placeholder} />;
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <PhoneNumber enabled={enabled} field={field} ans={answer} />;
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return <LongText field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            return <MultipleChoiceField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return <CheckboxField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return <DropdownField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_RANKING:
            return <RankingField field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_MEDIA:
            return <FileUpload field={field} ans={answer} enabled={enabled} />;
        case FormBuilderTagNames.INPUT_RATING:
            return <RatingField field={field} ans={answer} enabled={enabled} />;
        default:
            return <></>;
    }
};

interface IBetterCollectedFormProps {
    form: StandardFormDto;
    enabled?: boolean;
    isCustomDomain?: boolean;
    response?: StandardFormResponseDto;
    isPreview?: boolean;
    closeModal?: () => void;
    isDisabled?: boolean;
    isTemplate?: boolean;
}

export default function BetterCollectedForm({ form, enabled = false, response, isCustomDomain = false, isPreview = false, closeModal, isDisabled = false, isTemplate = false }: IBetterCollectedFormProps) {
    const router = useRouter();
    const { t } = useTranslation();

    const auth = useAppSelector(selectAuth);
    const formId = useAppSelector((state) => state.fillForm.id);
    const responseDataOwnerField = useAppSelector(selectFormResponderOwnerField);
    const invalidFields = useAppSelector(selectInvalidFields);
    const workspace = useAppSelector(selectWorkspace);
    const answers = useAppSelector(selectAnswers);

    const { openModal, closeModal: closeDialogModal } = useModal();
    const { openModal: openFullScreenModal, closeModal: closeFullScreenModal } = useFullScreenModal();

    const { files, resetFormFiles } = useFormAtom();

    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();

    const [submitResponse, { data }] = useSubmitResponseMutation();

    const [updatedForm, setUpdatedForm] = useState<StandardFormDto>(form);
    const [isFormSubmitted, setIsFormSubmitted] = useState(false);

    const conditionalFields = form?.fields?.filter((field: StandardFormFieldDto) => field?.type == FormBuilderTagNames.CONDITIONAL);

    const affectingFieldIds = Array.from(new Set(conditionalFields.flatMap((field) => field?.properties?.conditions.map((condition: Condition) => condition.field?.id)).filter((id) => id !== undefined)));

    const updateFormWithActions = () => {
        let formToUpdate: any = { ...form };
        const updatedForm = validateConditionsAndReturnUpdatedForm(formToUpdate, answers, conditionalFields);
        setUpdatedForm(updatedForm);
    };

    useEffect(
        () => {
            updateFormWithActions();
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        affectingFieldIds.map((fieldId: string) => answers[fieldId])
    );

    useEffect(() => {
        setUpdatedForm(form);
        updateFormWithActions();
    }, [form]);

    useEffect(() => {
        if (formId !== form.formId) {
            resetFormFiles();
            asyncDispatch(resetFillForm()).then(() => {
                dispatch(setFillFormId(form.formId));
                dispatch(setDataResponseOwnerField(form?.settings?.responseDataOwnerField || ''));
            });
        } else {
            dispatch(setFillFormId(form.formId));
            dispatch(setDataResponseOwnerField(form?.settings?.responseDataOwnerField || ''));
        }
    }, [form]);

    const [isResponseValid, setResponseValid] = useState(true);

    const onFormSubmitCallback = async (consentAnswers: Record<string, ConsentAnswerDto>, anonymize = false) => {
        if (isPreview) {
            openFullScreenModal('FORM_BUILDER_PREVIEW', { isFormSubmitted: true });
            return;
        }
        const formData = new FormData();
        // Append files to formData
        files.forEach((fileObj) => {
            formData.append('files', fileObj.file, fileObj.fileName);
            formData.append('file_field_ids', fileObj.fieldId);
            formData.append('file_ids', fileObj.fileId);
        });
        const responseExpirationType = form?.settings?.responseExpirationType;
        const responseExpiration = form?.settings?.responseExpiration;

        let responseExpirationTime = '';
        if (responseExpirationType === 'date') {
            responseExpirationTime = new Date(responseExpiration || '').toISOString();
        } else if (responseExpirationType === 'days') {
            const expiryDate = new Date();
            expiryDate.setDate(expiryDate.getDate() + parseInt(responseExpiration || ''));
            responseExpirationTime = expiryDate.toISOString();
        }

        const postBody = {
            form_id: form?.formId,
            answers: answers,
            form_version: form?.version || 1,
            consent: Object.values(consentAnswers),
            expiration: responseExpirationTime,
            expirationType: responseExpirationType,
            dataOwnerIdentifier: (answers && answers[responseDataOwnerField]?.email) || null,
            anonymize: anonymize
        };

        formData.append('response', JSON.stringify(postBody));

        const response: any = await submitResponse({ workspaceId: workspace.id, formId: form?.formId, body: formData });
        if (response?.data) {
            setIsFormSubmitted(true);
        } else {
            toast('Error submitting response', { type: 'error' });
        }
        closeFullScreenModal();
    };
    const onSubmitForm = async (event: any) => {
        event.preventDefault();
        if (isTemplate) return;
        const invalidFields: Record<string, Array<FormValidationError>> = {};
        let isResponseValid = true;
        updatedForm?.fields.forEach((field: StandardFormFieldDto, index: number) => {
            const validationErrors = validateFormFieldAnswer(field, answers[field.id]);
            if (validationErrors.length > 0) {
                setResponseValid(false);
                isResponseValid = false;
            }
            invalidFields[field.id] = validationErrors;
        });
        dispatch(setInvalidFields(invalidFields));
        if (!isResponseValid) {
            let firstInvalidFieldId = '';
            for (let field of updatedForm.fields) {
                if (Object.keys(invalidFields).includes(field.id) && invalidFields[field.id].length > 0) {
                    firstInvalidFieldId = field.id;
                    break;
                }
            }
            document.getElementById(firstInvalidFieldId)?.scrollIntoView({
                behavior: 'smooth',
                inline: 'center',
                block: 'center'
            });
            const errorInputDiv = document.getElementById(`input-${firstInvalidFieldId}`);
            errorInputDiv?.focus({ preventScroll: true });
            return;
        }
        setResponseValid(true);
        if (isPreview) {
            openFullScreenModal('CONSENT_FULL_MODAL_VIEW', {
                form: form,
                isPreview: true,
                onFormSubmit: onFormSubmitCallback
            });
            return;
        }
        openFullScreenModal('CONSENT_FULL_MODAL_VIEW', { form: form, onFormSubmit: onFormSubmitCallback });
    };

    useEffect(() => {
        return () => {
            resetFillForm();
            resetFormFiles();
        };
    }, []);

    const [trigger] = useLogoutMutation();

    const onClickSwitchAccount = async () => {
        trigger().then(async () => {
            router.push({
                pathname: '/login',
                query: {
                    type: 'responder',
                    workspace_id: workspace.id,
                    redirect_to: router.asPath
                }
            });
        });
    };

    const handleLogout = () => {
        openModal('LOGOUT_VIEW', { workspace, isClientDomain: true, skipRedirect: true });
    };

    if (isFormSubmitted) {
        return <ThankYouPage isDisabled={isDisabled} form={form} showSubmissionNumber={!!form?.settings?.showSubmissionNumber} submissionNumber={data} />;
    }

    return (
        <div className="w-full bg-white">
            {updatedForm?.coverImage && (
                <div className={`relative z-0 w-full flex aspect-banner-mobile lg:aspect-banner-desktop`}>
                    <Image layout="fill" objectFit="cover" src={updatedForm.coverImage} alt="test" className="brightness-75" />
                </div>
            )}
            <form
                className="w-full max-w-[700px] mx-auto px-10 pb-10 bg-white flex rounded-lg flex-col items-start "
                onKeyDown={(event: any) => {
                    if (!event.shiftKey && event.key === 'Enter') {
                        event.preventDefault();
                    }
                }}
                onSubmit={onSubmitForm}
            >
                {updatedForm?.logo && (
                    <div className={`relative ${updatedForm?.coverImage ? '-top-12' : 'mt-[60px]'} rounded-lg w-[100px] h-[100px] flex flex-col justify-center items-center gap-3 cursor-pointer hover:shadow-logoCard`}>
                        <Image height={100} width={100} objectFit="cover" src={updatedForm.logo} alt="logo" className="rounded-lg hover:bg-black-100" />
                    </div>
                )}
                <div className={`mb-6 ${updatedForm?.coverImage && updatedForm?.logo ? '' : 'mt-12'} w-full`}>
                    <div className="text-[32px] mb-2 font-bold text-black-800 flex w-full items-center justify-between">
                        <span>{updatedForm?.title || 'Untitled'}</span>
                        {enabled && (
                            <MenuDropdown
                                id="auth-menu"
                                className="!p-0"
                                showExpandMore={false}
                                menuTitle=""
                                menuContent={auth.id ? <AuthAccountProfileImage size={40} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} /> : <LoggedOutAccountIcon />}
                            >
                                {auth.id && (
                                    <div className="px-4 py-2 relative">
                                        <div className="flex gap-2">
                                            <AuthAccountProfileImage size={40} image={auth?.profileImage} name={getFullNameFromUser(auth) ?? ''} />
                                            <div className="flex flex-col gap-2 text-start justify-center !text-black-700 pr-1">
                                                <span className="body6 !leading-none">{getFullNameFromUser(auth)?.trim() || auth?.email || ''}</span>
                                                <span className="body5 !leading-none">{auth?.email} </span>
                                            </div>
                                        </div>
                                        <div className="pl-11 mt-2  p4-new">
                                            <span className="text-blue-500 cursor-pointer" onClick={onClickSwitchAccount}>
                                                Switch Account
                                            </span>
                                        </div>
                                        <div className="absolute text-black-600 top-0 right-2">
                                            <Close />
                                        </div>

                                        {!form?.settings?.requireVerifiedIdentity && (
                                            <>
                                                <Divider className="text-black-200 mt-4" />
                                                <div className="mt-2 py-2 px-4  flex  gap-2 text-black-800 hover:bg-new-blue-100 rounded cursor-pointer active:bg-blue-100" onClick={handleLogout}>
                                                    <Logout width={24} height={24} />
                                                    <span className="font-medium">Log Out</span>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                )}
                                {!auth.id && (
                                    <div className="px-4 py-2">
                                        <div className="p2-new text-black-600 mb-2">Do you wish to track your form response for future reference?</div>
                                        <div
                                            className="p2-new text-blue-500 cursor-pointer hover:underline"
                                            onClick={() => {
                                                router.push({
                                                    pathname: '/login',
                                                    query: {
                                                        type: 'responder',
                                                        workspace_id: workspace.id,
                                                        redirect_to: router.asPath
                                                    }
                                                });
                                            }}
                                        >
                                            Sign In and start tracking
                                        </div>
                                    </div>
                                )}
                            </MenuDropdown>
                        )}
                    </div>

                    {updatedForm?.description && <div className="text-[16px] font-normal text-black-700">{updatedForm?.description}</div>}
                </div>

                <div className="flex flex-col w-full gap-2">
                    {updatedForm?.fields?.map((field: StandardFormFieldDto) => (
                        <div key={field?.id} className="relative w-full" id={field?.id}>
                            {!field?.properties?.hidden && renderFormField(field, enabled, response?.answers[field.id] || answers[field.id], updatedForm?.fields)}
                            <FieldValidations field={field} inValidations={invalidFields[field?.id]} />
                        </div>
                    ))}
                    <div className={'mt-10'}>
                        {!isResponseValid && <div className="text-red-500 mb-2 text-sm">*Invalid answers in one or more fields. Check and correct the highlighted entries.</div>}
                        <AppButton variant={ButtonVariant.Secondary} type="submit" disabled={!enabled}>
                            {updatedForm?.buttonText || 'Submit'}
                        </AppButton>
                    </div>
                </div>
            </form>
        </div>
    );
}
