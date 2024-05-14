'use client';

import React, {useEffect} from 'react';

import {useRouter} from 'next/navigation';

import cn from 'classnames';

import {useModal} from '@app/components/modal-views/context';
import {defaultForm} from '@app/constants/form';
import {getDefaultImageFromUnsplash} from '@app/lib/getDefaultImageFromUnsplash';
import {Sheet, SheetContent, SheetTrigger} from '@app/shadcn/components/ui/sheet';
import {useAppSelector} from '@app/store/hooks';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import {useCreateV2FormMutation} from '@app/store/redux/formApi';
import {useCreateFormFromTemplateMutation, useGetTemplatesQuery} from '@app/store/redux/templateApi';
import {selectWorkspace} from '@app/store/workspaces/slice';
import {GoogleFormIcon} from '@app/views/atoms/Icons/GoogleForm';
import FormTypeSelectionComponent from '@app/views/molecules/FormBuilder/FormTypeSelectionComponent';
import NavBar from '@app/views/molecules/FormBuilder/Navbar';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';
import useDrivePicker from '@fyelci/react-google-drive-picker';
import {useIsMobile} from '@app/lib/hooks/use-breakpoint';
import {useDialogModal} from "@app/lib/hooks/useDialogModal";
import AIIcon from "@app/views/atoms/Icons/AIIcon";

const CardVariants = {
    blue: 'text-blue-500 hover:bg-blue-100 transition hover:border-blue-100',
    purple: 'text-purple-500 hover:bg-purple-100 transition  hover:border-purple-100',
    pink: 'text-pink-500 hover:bg-pink-100 hover:border-pink-100 transition-all'
};

export default function CreateFormPage({searchParams}: { searchParams: { modal?: string } }) {
    const [createV2Form] = useCreateV2FormMutation();
    const {resetFields} = useFormFieldsAtom();
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [openPicker] = useDrivePicker();
    const {openModal} = useModal();
    const {openDialogModal} = useDialogModal()
    const isMobile = useIsMobile();

    const showModal = searchParams.modal;

    useEffect(() => {
        if (showModal === 'true') {
            openModal('IMPORT_FORMS', {nonClosable: true});
        }
    }, [showModal]);

    const {data: templates} = useGetTemplatesQuery({v2: true});

    const [createFormFrmTemplate] = useCreateFormFromTemplateMutation();

    const handleCreateForm = async (type: string) => {
        const isMultiPage = type === 'Modern Form';
        resetFields();
        const imageResponse = await getDefaultImageFromUnsplash('New minimal');
        const newPics = imageResponse?.response?.results;
        const randomIndexes = Array.from({length: 3}, () => Math.floor(Math.random() * 10));
        const pic = newPics?.filter((item: any, index: number) => randomIndexes.includes(index));
        const updatedForm = {...defaultForm};
        updatedForm.fields[0].imageUrl = (pic && pic[1]?.urls?.full) || 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp';
        updatedForm.welcomePage!.imageUrl = (pic && pic[0]?.urls?.full) || 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp';
        updatedForm.thankyouPage![0].imageUrl = (pic && pic[2]?.urls?.full) || 'https://s3.eu-central-1.wasabisys.com/bettercollected/images/v2_layout_image.webp';
        const formBody = {...updatedForm, builderVersion: 'v2', isMultiPage};
        const formData = new FormData();
        formData.append('form_body', JSON.stringify(formBody));
        const apiRequestBody: any = {workspaceId: workspace.id, body: formData};
        const response: any = await createV2Form(apiRequestBody);
        if (response?.data) {
            router.replace(`/${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit?showTitle=true`);
        }
    };

    const createFormFromTemplate = async (templateId: string) => {
        const response: any = await createFormFrmTemplate({
            workspace_id: workspace.id,
            template_id: templateId
        });
        const editFormUrl = `/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`;
        router.push(editFormUrl);
    };

    return (
        <div className="min-h-screen bg-white">
            <NavBar/>
            <div className="px-auto flex h-full flex-col justify-center lg:flex-row ">
                <div className=" flex w-full max-w-[1330px] flex-col px-5 md:px-10">
                    <div className="h3-new text-black-800 mb-4 mt-6">New Form</div>
                    <div className="flex w-full flex-col flex-wrap gap-6 lg:flex-row">
                        {isMobile ? (
                            <Card variant={'blue'} icon={<PlusIcon/>} content={'Create New Form'} onClick={() => {
                            }}/>
                        ) : (
                            <Sheet>
                                <SheetTrigger asChild>
                                    <Card variant={'blue'} icon={<PlusIcon/>} content={'Create New Form'}
                                          onClick={() => {
                                          }}/>
                                </SheetTrigger>
                                <SheetContent className=" shadow-v2 h-full w-full p-0 drop-shadow-2xl" side={'top'}
                                              hideCloseIcon>
                                    <div className="h-full w-full bg-white ">
                                        <NavBar isModal/>
                                        <FormTypeSelectionComponent handleCreateForm={handleCreateForm}/>
                                    </div>
                                </SheetContent>
                            </Sheet>
                        )}

                        <Card
                            variant={'purple'}
                            icon={<GoogleFormIcon width={30} height={30} className="mb-2 w-full text-purple-500"/>}
                            content={'Import Google Form'}
                            onClick={() => {
                                openModal('IMPORT_FORMS', {nonClosable: true});
                            }}
                        />
                        <Card variant={'pink'} icon={<AIIcon className="text-[#FE3678]"/>} content={'Start with AI'}
                              onClick={() => {
                                  if (!isMobile)
                                      openDialogModal("START_WITH_AI")
                              }}/>
                    </div>

                    {!isMobile && (
                        <>
                            <div className="h3-new text-black-800 mb-4 mt-12">Templates</div>
                            <div className="flex w-full flex-row flex-wrap gap-x-6 gap-y-10  ">
                                {templates?.map((template) => (
                                    <div
                                        className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500"
                                        key={template?.id} onClick={() => createFormFromTemplate(template.id)}>
                                        <div className="relative h-[157px] w-[281px] overflow-hidden rounded-md">
                                            <div className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]"
                                                 style={{transformOrigin: 'top left'}}>
                                                <LayoutWrapper showDesktopLayout theme={template?.theme} disabled
                                                               layout={template.welcomePage?.layout}
                                                               imageUrl={template?.welcomePage?.imageUrl}>
                                                    <WelcomePage isPreviewMode theme={template?.theme}
                                                                 welcomePageData={template?.welcomePage}/>
                                                </LayoutWrapper>
                                            </div>
                                        </div>
                                        <div className="p2-new mt-2 !font-medium">{template.title}</div>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

interface CardWrapperProps {
    icon: React.ReactNode;
    content: React.ReactNode;
    onClick: React.MouseEventHandler<HTMLDivElement>;
    variant: 'blue' | 'purple' | 'pink';
    addSoon?: boolean;
    soonMsg?: string;
}

const Card = ({icon, content, onClick, variant, addSoon, soonMsg}: CardWrapperProps) => {
    return (
        <div
            className={cn('border-black-300 relative flex h-[170px] w-full cursor-pointer flex-col items-center justify-center overflow-hidden rounded-lg border bg-white lg:h-[117px] lg:w-[220px]', CardVariants[variant])}
            onClick={onClick}>
            {icon}
            <span className="p3-new text-black-800 mb-1 mt-2">{content}</span>
            {content !== 'Import Google Form' && <OnlyAvailableInDesktopVersion/>}
            {addSoon && <SoonComponent msg={soonMsg}/>}
        </div>
    );
};

const SoonComponent = ({msg}: { msg?: string }) => {
    return (
        <div
            className="bg-new-pink absolute bottom-0 left-1/3 flex h-fit w-full -rotate-[30deg] items-center justify-center text-[10px] font-medium leading-none text-white">
            <span className=" ml-14 md:ml-4">{msg || 'Soon'}</span>
        </div>
    );
};

const OnlyAvailableInDesktopVersion = () => {
    return (
        <div
            className="bg-new-pink absolute -right-10 bottom-3 flex h-auto w-[200px] -rotate-[30deg] flex-col items-center justify-center gap-1 py-2 text-[10px] font-medium leading-none text-white lg:hidden">
            <span className="  md:ml-4">Only available in</span>
            <span className="  md:ml-4">desktop version</span>
        </div>
    );
};

const PlusIcon = () => {
    return (
        <svg width="41" height="40" viewBox="0 0 41 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 11L20 29" stroke="#0764EB" strokeWidth="2" strokeLinecap="round"/>
            <path d="M11 20H29" stroke="#0764EB" strokeWidth="2" strokeLinecap="round"/>
        </svg>
    );
};


