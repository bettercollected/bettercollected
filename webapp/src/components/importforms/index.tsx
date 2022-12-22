import { useState } from 'react';

import { useRouter } from 'next/router';

import FormControl from '@mui/material/FormControl';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import Loader from '@app/components/ui/loader';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { GoogleMinifiedFormDto } from '@app/models/dtos/googleForm';
import { useGetMinifiedFormsQuery, useImportFormMutation, useLazyGetGoogleFormQuery } from '@app/store/forms/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function ImportForms() {
    const { closeModal } = useModal();
    const breakpoint = useBreakpoint();
    const [selectedForm, setSelectedForm] = useState('');
    const [responseDataOwner, setResponseDataOwner] = useState('');
    const [stepCount, setStepCount] = useState(0);

    const minifiedForms = useGetMinifiedFormsQuery();
    const [googleFormTrigger, googleFormResult] = useLazyGetGoogleFormQuery();

    const [importForm, importFormResult] = useImportFormMutation();

    const router = useRouter();

    const handleConnectWithGoogle = () => {
        router.push(`${environments.API_ENDPOINT_HOST}/auth/google/connect`);
        console.log('got inside');
    };

    if (minifiedForms.isLoading) return <FullScreenLoader />;

    if (minifiedForms.isError)
        return (
            <div className="text-sm text-red-500 p-4 rounded-md shadow-md bg-white">
                <h2 className="mb-2">Oops! We&apos;ve encountered an issue.</h2>
                <Button variant="solid" size="small" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleConnectWithGoogle}>
                    Authorize Google
                </Button>
            </div>
        );

    const handleBack = (e: any) => {
        setStepCount(stepCount - 1);
        setResponseDataOwner('');
        setSelectedForm('');
    };

    const handleNext = async (e: any) => {
        setStepCount(stepCount + 1);
        await googleFormTrigger(selectedForm);
    };

    const handleImportForm = async () => {
        const form: any = { ...googleFormResult?.data?.payload?.content, provider: 'google' };
        await importForm({ form, response_data_owner: responseDataOwner })
            .then(() => closeModal())
            .catch((e) => toast.error('Could not import the form.'));
    };

    const handleSelectDataResponseOwner = (e: any) => {
        setResponseDataOwner(e.target.value);
    };

    const GoogleFormMinifiedCard = ({ form }: { form: GoogleMinifiedFormDto }) => {
        return (
            <div
                onClick={() => setSelectedForm(form.id)}
                className={`flex border-[1.5px] cursor-pointer justify-between items-center p-2 mb-2 mr-3 rounded-lg ${selectedForm === form.id ? 'border-blue-500' : 'border-gray-100 hover:bg-gray-50 hover:border-gray-50'} `}
            >
                <div className="w-full mr-2">
                    <p className="text-[9px] md:text-sm !m-0 !p-0 text-gray-400 italic">{toEndDottedStr(form.id, 30)}</p>
                    <p className="text-xs md:text-base font-semibold text-grey p-0">{toEndDottedStr(form.name, 40)}</p>
                </div>
            </div>
        );
    };

    const GoogleFormData = () => {
        if (googleFormResult.isFetching)
            return (
                <div className="flex w-full h-full items-center justify-center">
                    <Loader />
                </div>
            );
        if (googleFormResult.isError) return <p className="text-sm text-red-500">Oops! We&apos;ve encountered an issue.</p>;
        const form = googleFormResult?.data?.payload?.content;
        return (
            <div className="flex flex-col w-full">
                {form?.info?.title && <p className="max-w-[360px] text-sm md:text-base font-semibold text-grey mb-2 p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.info?.title, 15) : toEndDottedStr(form?.info?.title, 30)}</p>}
                {form?.info?.description && (
                    <p className="max-w-[360px] text-sm text-softBlue mb-2 p-0 w-full">
                        {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.info?.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.info?.description, 80) : toEndDottedStr(form?.info?.description, 140)}
                    </p>
                )}
                {!form?.info?.description && <p className="text-sm text-softBlue mb-2 p-0 w-full italic">Form description not available.</p>}
                {form?.items && Array.isArray(form?.items) && (
                    <>
                        <hr />
                        <p className="max-w-[360px] text-sm font-semibold text-grey my-2">Select another data response owner if collect emails is disabled in your form</p>
                        <FormControl fullWidth>
                            <Select placeholder="Select one of the fields" value={responseDataOwner} onChange={handleSelectDataResponseOwner}>
                                {form?.items.map(
                                    (item) =>
                                        item?.questionItem?.question?.questionId && (
                                            <MenuItem key={item.itemId} value={item?.questionItem?.question?.questionId}>
                                                {item.title}
                                            </MenuItem>
                                        )
                                )}
                            </Select>
                        </FormControl>
                    </>
                )}
            </div>
        );
    };

    return (
        <div className="m-auto w-full items-start justify-between rounded-lg bg-white">
            <div className="flex flex-col items-center gap-8 justify-between p-10">
                <div className="flex flex-row items-start border-b-[1px] pb-1 border-[#eaeaea] justify-between">
                    <div className="flex flex-col">
                        {!!stepCount ? (
                            <Button className="w-fit z-10 !h-[34px] mb-3 rounded-lg hover:!-translate-y-0 focus:-translate-y-0" variant="solid" onClick={handleBack}>
                                <LongArrowLeft width={15} height={15} />
                            </Button>
                        ) : (
                            <div className="!h-[34px] mb-3" />
                        )}
                        <h2 className="text-md md:text-lg text-left font-bold">Import Forms</h2>
                        <p className="text-[#00000082] text-sm md:text-md">Select the forms you wish to import to Better Collected.</p>
                    </div>
                    <div onClick={() => closeModal()} className="border-[1.5px] border-gray-200 hover:shadow hover:text-black cursor-pointer rounded-full p-3">
                        <Close className="cursor-pointer text-gray-600 hover:text-black" />
                    </div>
                </div>
                <div className="w-full h-[250px] scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-300 overflow-y-scroll scrollbar-thumb-rounded-full scrollbar-track-rounded-full">
                    {!stepCount ? (
                        <>
                            {minifiedForms?.data?.payload?.content.map((form: GoogleMinifiedFormDto, idx: any) => (
                                <GoogleFormMinifiedCard key={form.id} form={form} />
                            ))}
                        </>
                    ) : (
                        <GoogleFormData />
                    )}
                </div>
                <div className="flex w-full justify-between">
                    {!stepCount ? (
                        <Button isLoading={minifiedForms.isLoading} disabled={!selectedForm} variant="solid" className={`!rounded-lg !h-10 !m-0 ${!selectedForm ? '' : '!bg-blue-500'}`} onClick={handleNext}>
                            Next
                        </Button>
                    ) : (
                        <Button
                            isLoading={importFormResult.isLoading}
                            disabled={!googleFormResult?.data?.payload?.content}
                            variant="solid"
                            className={`!rounded-lg !h-10 !m-0 ${!googleFormResult?.data?.payload?.content ? '' : '!bg-blue-500'}`}
                            onClick={handleImportForm}
                        >
                            Import
                        </Button>
                    )}
                    <Button variant="transparent" className="!rounded-lg !h-10 !m-0 !border-gray border-[1px] !border-solid" onClick={() => closeModal()}>
                        Cancel
                    </Button>
                </div>
            </div>
        </div>
    );
}
