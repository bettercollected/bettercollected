import { useEffect, useState } from 'react';

import FormControlLabel from '@mui/material/FormControlLabel';
import Switch, { SwitchProps } from '@mui/material/Switch';
import { styled } from '@mui/material/styles';
import { toast } from 'react-toastify';

import { GoogleMinifiedFormDto } from '@app/models/dtos/googleForm';
import { useGetMinifiedFormsQuery, useImportFormsMutation } from '@app/store/google/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

import { useModal } from '../modal-views/context';
import Button from '../ui/button';
import FullScreenLoader from '../ui/fullscreen-loader';

const IOSSwitch = styled((props: SwitchProps) => <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />)(({ theme }) => ({
    width: 42,
    height: 26,
    padding: 0,
    '& .MuiSwitch-switchBase': {
        padding: 0,
        margin: 2,
        transitionDuration: '300ms',
        '&.Mui-checked': {
            transform: 'translateX(16px)',
            color: '#fff',
            '& + .MuiSwitch-track': {
                backgroundColor: theme.palette.mode === 'dark' ? '#2ECA45' : '#65C466',
                opacity: 1,
                border: 0
            },
            '&.Mui-disabled + .MuiSwitch-track': {
                opacity: 0.5
            }
        },
        '&.Mui-focusVisible .MuiSwitch-thumb': {
            color: '#33cf4d',
            border: '6px solid #fff'
        },
        '&.Mui-disabled .MuiSwitch-thumb': {
            color: theme.palette.mode === 'light' ? theme.palette.grey[100] : theme.palette.grey[600]
        },
        '&.Mui-disabled + .MuiSwitch-track': {
            opacity: theme.palette.mode === 'light' ? 0.7 : 0.3
        }
    },
    '& .MuiSwitch-thumb': {
        boxSizing: 'border-box',
        width: 22,
        height: 22
    },
    '& .MuiSwitch-track': {
        borderRadius: 26 / 2,
        backgroundColor: theme.palette.mode === 'light' ? '#E9E9EA' : '#39393D',
        opacity: 1,
        transition: theme.transitions.create(['background-color'], {
            duration: 500
        })
    }
}));

export default function ImportForms() {
    const { closeModal } = useModal();

    const [enabledFormList, setEnabledFormList] = useState<any>([]);

    const [forms, setForms] = useState<Array<GoogleMinifiedFormDto>>([]);

    const { data, isLoading, refetch } = useGetMinifiedFormsQuery();

    const importFormsMutation = useImportFormsMutation();

    useEffect(() => {
        if (data) {
            setForms(data?.payload?.content);
        }
    }, [data]);

    if (isLoading) return <FullScreenLoader />;

    const handleImportForms = () => {
        const [importForms] = importFormsMutation;
        importForms(enabledFormList)
            .then((data: any) => {
                toast.info(data?.data?.status);
                closeModal();
            })
            .catch((e) => {
                toast.error('An Error occured');
            });
    };

    const FooterRenderer = () => {
        return (
            <div className="flex w-full justify-between">
                <Button isLoading={importFormsMutation[1].isLoading} disabled={enabledFormList.length === 0} variant="solid" className={`!rounded-lg !h-10 !m-0 ${!enabledFormList.length ? '' : '!bg-blue-500'}`} onClick={handleImportForms}>
                    Import ({enabledFormList.length})
                </Button>
                <Button variant="transparent" disabled={importFormsMutation[1].isLoading} className="!rounded-lg !h-10 !m-0 !border-gray border-[1px] !border-solid" onClick={() => closeModal()}>
                    Cancel
                </Button>
            </div>
        );
    };

    const checkIfSwitchIsEnabled = (title: string) => {
        return enabledFormList.includes(title);
    };

    const CardRenderer = ({ form }: { form: GoogleMinifiedFormDto }) => {
        const { name, id } = form;

        const handleSwitchEnable = () => {
            if (enabledFormList.includes(id)) {
                const tempArray = enabledFormList.filter((enabledFormId: string) => id !== enabledFormId);
                setEnabledFormList([...tempArray]);
            } else {
                setEnabledFormList([...enabledFormList, id]);
            }
        };

        return (
            <div onClick={handleSwitchEnable} className="flex border-[1.5px] border-gray-100 hover:bg-blue-50 hover:border-blue-50 cursor-pointer justify-between items-center p-2 mb-2 mr-3 rounded-lg">
                <div className="w-full mr-2">
                    <p className="text-[9px] !m-0 !p-0 text-gray-400 italic">{toEndDottedStr(id, 30)}</p>
                    <p className="text-xs font-semibold text-grey p-0">{toEndDottedStr(name, 40)}</p>
                </div>

                <FormControlLabel className="m-0" label="" control={<IOSSwitch checked={checkIfSwitchIsEnabled(form.id)} />} />
            </div>
        );
    };

    const CardContainerRenderer = () => {
        return (
            <>
                {forms.map((form: GoogleMinifiedFormDto, idx: any) => (
                    <CardRenderer key={form.id} form={form} />
                ))}
            </>
        );
    };

    const HeadingRenderer = () => (
        <div className="flex flex-row items-start border-b-[1px] pb-1 border-[#eaeaea] justify-between">
            <div className="flex flex-col">
                <h2 className="text-md text-left font-bold">Import Forms</h2>
                <p className="text-[#00000082] text-sm">Select the forms you wish to import to Better Collected.</p>
            </div>
            <div className="cursor-pointer text-gray-600 hover:text-black" onClick={() => closeModal()}>
                X
            </div>
        </div>
    );

    return (
        <div className="m-auto w-full items-start justify-between rounded-lg bg-white scale-110">
            <div className="flex flex-col items-center gap-8 justify-between p-10">
                <HeadingRenderer />
                <div className="w-full h-[250px] scrollbar-thin scrollbar-thumb-gray-400 scrollbar-track-gray-300 overflow-y-scroll scrollbar-thumb-rounded-full scrollbar-track-rounded-full">
                    <CardContainerRenderer />
                </div>
                <FooterRenderer />
            </div>
        </div>
    );
}
