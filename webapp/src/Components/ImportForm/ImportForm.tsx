import React, {useCallback, useEffect, useState} from "react";
import GoogleFolder from "@app/assets/images/google_folder.png";
import Image from 'next/image';
import AppTextField from "@Components/Common/Input/AppTextField";
import {LinkIcon} from "@app/components/icons/link-icon";
import GoogleForm from "@app/assets/images/google_form.png";
import _ from 'lodash'
import {CircularProgress} from "@mui/material";
import {useImportFormMutation, useLazyGetSingleFormFromProviderQuery} from "@app/store/workspaces/api";
import {toast} from "react-toastify";
import {toastMessage} from "@app/constants/locales/toast-message";
import {useTranslation} from "next-i18next";
import {useAppSelector} from "@app/store/hooks";

interface IAutoCompleteFormFieldProps {
    label: string;
    questionId: string;
}

const ImportForm = () => {
    const {t} = useTranslation();
    const [importFormLink, setImportFormLink] = useState("")
    const [formId, setFormId] = useState("")
    const [error, setError] = useState(false)
    const [errorMessage, setErrorMessage] = useState('')
    const [showErrorView, setShowError] = useState(false)
    const [isLoading, setIsLoading] = useState(false)
    const [responseDataOwner, setResponseDataOwner] = useState<IAutoCompleteFormFieldProps | null>(null);

    const [importForm, importFormResult] = useImportFormMutation();
    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();

    const workspace = useAppSelector((state) => state.workspace);

    const checkFormUrlPattern = useCallback((_.debounce((importFormLink) => {
        const pattern = /https:\/\/docs\.google\.com\/forms\/d\/([^/]+)\/edit/;
        const match = importFormLink.match(pattern);
        setIsLoading(false)
        if (match) {
            const formId = match[1];
            setFormId(formId)
            setError(false)
            handleImportForm(formId)
        } else {
            setFormId("");
            setError(true)
            setErrorMessage('Oops! That URL doesnot look quite right. Could you double-check it ? Hint: The URL ends with “/edit” at the end.')
        }
    }, 1000)), [importFormLink])

    const cleanup = () => {
        setResponseDataOwner(null);
    };

    useEffect(() => {
        setIsLoading(importFormResult.isLoading || singleFormFromProviderResult.isLoading)
    }, [importFormResult.isLoading, singleFormFromProviderResult.isLoading]);

    const handleImportForm = async (formId: string) => {
        const singleForm = await singleFormFromProviderTrigger({provider: "google", formId: formId})
        const form: any = {...singleForm?.data, provider: 'google'};
        delete form['clientFormItems'];
        if (singleForm.error) {
            setError(true)
            if (singleForm?.error?.status === 401)
                setErrorMessage('Uh-oh! Looks like you need permission to access this form. Maybe check with the owner!')
            if (singleForm?.error?.status === 404) {
                setErrorMessage('Uh-oh! It seems like form you are trying to fetch does not exist in Google Forms.')
            }
            return
        }
        const response: any = await importForm({
            body: {form, response_data_owner: responseDataOwner?.questionId ?? ''},
            provider: 'google',
            workspaceId: workspace.id
        });
        if (response.data) {
            toast.success(t(toastMessage.formImportedSuccessfully).toString());
        } else {
            setError(true)
            setErrorMessage('error')
            toast.error(response.error?.data || t(toastMessage.couldNotImportedForm));
        }
    };

    useEffect(() => {
        if (importFormLink) {
            setIsLoading(true);
            setError(false)
            checkFormUrlPattern(importFormLink);
        }
    }, [importFormLink])

    const getLoadingTextType = () => {
        if (importFormResult?.isLoading) {
            return 'Importing Form'
        } else if (singleFormFromProviderResult?.isLoading) {
            return 'Fetching Form'
        } else return 'Checking form URL'
    }


    return <div className={'flex flex-col items-center gap-4 md:w-[500px]'}>
        <Image className={'pb-1'} src={GoogleFolder} alt={'GoogleFolder'}/>
        <h1 className={'h3-new !text-black-800'}>Import Google Form <span className={'!text-pink-500'}> From URL</span>
        </h1>
        <h4 className={'body4 !text-black-700  text-center pb-6'}>Use the editing URL directly from the top of the
            Google browser bar, not the shared form link.</h4>
        <AppTextField placeholder={'Paste URL'} className={'w-full'} icon={<LinkIcon/>} value={importFormLink}
                      onChange={(event) => {
                          setImportFormLink(event.target.value)
                      }}/>
        <div className={'flex gap-1 pb-8 justify-start w-full h-20'}>
            {
                importFormLink && isLoading ?
                    <LoadingIconWithText text={getLoadingTextType()}/>
                    :
                    error &&
                    <span className={'body4 !text-red-500'}>{errorMessage}</span>
            }
        </div>
        <Image src={GoogleForm} alt={'GoogleForm'}/>
    </div>
}
export default ImportForm

const LoadingIconWithText = ({text}: { text: string }) => {
    return <div className={'flex gap-2'}><CircularProgress size={20}/> <span
        className={'body4 !text-black-700'}>{text}</span>
    </div>
}
