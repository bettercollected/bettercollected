import { useEffect, useState } from 'react';

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
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useAppSelector } from '@app/store/hooks';
import { useGetTypeformsQuery, useImportTypeFormMutation, useLazyGetTypeformQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function ImportTypeForms() {
    const { closeModal } = useModal();

    const typeforms = useGetTypeformsQuery();

    const breakpoint = useBreakpoint();

    const [importTypeFormTrigger, importTypeFormResult] = useImportTypeFormMutation();

    const [typeFormTrigger, typeFormResult] = useLazyGetTypeformQuery();

    const workspace = useAppSelector((state) => state.workspace);

    const [showSingleFormImport, setShowSingleFormImport] = useState(false);

    const [selectedForm, setSelectedForm] = useState('');

    const [responseDataOwner, setResponseDataOwner] = useState('');

    if (typeforms.isLoading) return <FullScreenLoader />;

    if (typeforms.isError)
        return (
            <div className="text-sm text-red-500 p-4 rounded-md shadow-md bg-white">
                <h2 className="mb-2">Oops! We&apos;ve encountered an issue.</h2>
                <a>
                    <Button variant="solid" size="small" className="ml-3 !w-full !rounded-xl !bg-blue-500">
                        Authorize typeform
                    </Button>
                </a>
            </div>
        );

    const handleBack = () => {
        setShowSingleFormImport(false);
    };

    const TypeFormMinifiedCard = ({ form }: { form: any }) => {
        return (
            <div
                onClick={() => setSelectedForm(form.id)}
                className={`flex border-[1.5px] cursor-pointer justify-between items-center p-2 mb-2 mr-3 rounded-lg ${selectedForm === form.id ? 'border-blue-500' : 'border-gray-100 hover:bg-gray-50 hover:border-gray-50'} `}
            >
                <div className="w-full mr-2">
                    <p className="text-[9px] md:text-sm !m-0 !p-0 text-gray-400 italic">{toEndDottedStr(form.id, 30)}</p>
                    <p className="text-xs md:text-base font-semibold text-grey p-0">{toEndDottedStr(form.title, 40)}</p>
                </div>
            </div>
        );
    };

    const handleSelectDataResponseOwner = (e: any) => {
        setResponseDataOwner(e.target.value);
    };
    const TypeFormData = () => {
        if (typeFormResult.isFetching)
            return (
                <div className="flex w-full h-full items-center justify-center">
                    <Loader />
                </div>
            );

        if (typeFormResult.isError) return <p className="text-sm text-red-500">Oops! We&apos;ve encountered an issue.</p>;

        if (!typeFormResult.data) {
            return <></>;
        }

        return (
            <div className="flex flex-col w-full">
                {typeFormResult.data.title && (
                    <p className="max-w-[360px] text-sm md:text-base font-semibold text-grey mb-2 p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(typeFormResult.data.title, 15) : toEndDottedStr(typeFormResult.data.title, 30)}</p>
                )}
                {typeFormResult.data.description && (
                    <p className="max-w-[360px] text-sm text-softBlue mb-2 p-0 w-full">
                        {['xs', 'sm'].indexOf(breakpoint) !== -1
                            ? toEndDottedStr(typeFormResult.data.description, 45)
                            : ['md'].indexOf(breakpoint) !== -1
                            ? toEndDottedStr(typeFormResult.data.description, 80)
                            : toEndDottedStr(typeFormResult.data.description, 140)}
                    </p>
                )}

                {typeFormResult?.data?.fields && Array.isArray(typeFormResult?.data?.fields) && (
                    <>
                        <hr />
                        <p className="max-w-[360px] text-sm font-semibold text-grey my-2">Select another data response owner if collect emails is disabled in your form</p>
                        <FormControl fullWidth>
                            <Select placeholder="Select one of the fields" value={responseDataOwner} onChange={handleSelectDataResponseOwner}>
                                {typeFormResult?.data?.fields.map(
                                    (item: any) =>
                                        item?.id && (
                                            <MenuItem key={item.id} value={item?.id}>
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
                        {showSingleFormImport ? (
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
                {!showSingleFormImport &&
                    typeforms.data.map((typeform: any) => (
                        <div className="w-full" key={typeform.id}>
                            <TypeFormMinifiedCard form={typeform} />
                        </div>
                    ))}
                {showSingleFormImport && <TypeFormData />}

                <div className="flex w-full justify-between">
                    {!showSingleFormImport ? (
                        <Button
                            isLoading={typeforms.isLoading}
                            disabled={!selectedForm}
                            variant="solid"
                            className={`!rounded-lg !h-10 !m-0 ${!selectedForm ? '' : '!bg-blue-500'}`}
                            onClick={() => {
                                setShowSingleFormImport(true);
                                typeFormTrigger(selectedForm);
                            }}
                        >
                            Next
                        </Button>
                    ) : (
                        <Button
                            isLoading={typeFormResult.isLoading || importTypeFormResult.isLoading}
                            variant="solid"
                            className={`!rounded-lg !h-10 !m-0 !bg-blue-500`}
                            onClick={async () => {
                                const result: any = await importTypeFormTrigger({
                                    workspaceId: workspace.id,
                                    body: {
                                        form: typeFormResult.data,
                                        response_data_owner: responseDataOwner
                                    }
                                });

                                if (result.data) {
                                    toast('Form Imported!!!', {
                                        type: 'success'
                                    });
                                    closeModal();
                                }
                                if (result.isError) {
                                    toast('Error importing form !!!', {
                                        type: 'error'
                                    });
                                }
                            }}
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
