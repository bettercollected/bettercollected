'use client';

import React from 'react';

import { useRouter } from 'next/navigation';

import cn from 'classnames';

import { useModal } from '@app/components/modal-views/context';
import { defaultForm } from '@app/constants/form';
import { Sheet, SheetContent, SheetTrigger } from '@app/shadcn/components/ui/sheet';
import { useAppSelector } from '@app/store/hooks';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useCreateV2FormMutation } from '@app/store/redux/formApi';
import { useCreateFormFromTemplateMutation, useGetTemplatesQuery } from '@app/store/redux/templateApi';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { GoogleFormIcon } from '@app/views/atoms/Icons/GoogleForm';
import FormTypeSelectionComponent from '@app/views/molecules/FormBuilder/FormTypeSelectionComponent';
import NavBar from '@app/views/molecules/FormBuilder/Navbar';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';
import useDrivePicker from '@fyelci/react-google-drive-picker';

const CardVariants = {
    blue: 'text-blue-500 hover:bg-blue-100 transition hover:border-blue-100',
    purple: 'text-purple-500 hover:bg-purple-100 transition  hover:border-purple-100',
    pink: 'text-pink-500 !cursor-auto'
};

export default function CreateFormPage() {
    const [createV2Form] = useCreateV2FormMutation();
    const { resetFields } = useFormFieldsAtom();
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [openPicker] = useDrivePicker();
    const { openModal } = useModal();

    const { data: templates } = useGetTemplatesQuery({ v2: true });

    const [createFormFrmTemplate] = useCreateFormFromTemplateMutation();

    const handleCreateForm = async (type: string) => {
        const isMultiPage = type === 'Modern Form';
        resetFields();
        const formBody = { ...defaultForm, builderVersion: 'v2', isMultiPage };
        const formData = new FormData();
        formData.append('form_body', JSON.stringify(formBody));
        const apiRequestBody: any = { workspaceId: workspace.id, body: formData };
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
            <NavBar />
            <div className="px-auto flex h-full justify-center ">
                <div className=" flex max-w-[1330px] flex-col px-5 md:px-10">
                    <div className="h3-new text-black-800 mb-4 mt-6">New Form</div>
                    <div className="flex flex-wrap gap-6">
                        <Sheet>
                            <SheetTrigger asChild>
                                <Card variant={'blue'} icon={<PlusIcon />} content={'Create New Form'} onClick={() => {}} />
                            </SheetTrigger>
                            <SheetContent className=" shadow-v2 h-full w-full p-0 drop-shadow-2xl" side={'top'} hideCloseIcon>
                                <div className="h-full w-full bg-white ">
                                    <NavBar isModal />
                                    <FormTypeSelectionComponent handleCreateForm={handleCreateForm} />
                                </div>
                            </SheetContent>
                        </Sheet>

                        <Card
                            variant={'purple'}
                            icon={<GoogleFormIcon width={30} height={30} className="mb-2 text-purple-500" />}
                            content={'Import Google Form'}
                            onClick={() => {
                                openModal('IMPORT_FORMS', { nonClosable: true });
                            }}
                        />
                        <Card variant={'pink'} icon={<AIIcon />} content={'Start with AI'} onClick={() => {}} addSoon />
                    </div>

                    <div className="h3-new text-black-800 mb-4 mt-12">Templates</div>
                    <div className="flex w-full flex-row flex-wrap gap-x-6 gap-y-10  ">
                        {templates?.map((template) => (
                            <div className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500" key={template?.id} onClick={() => createFormFromTemplate(template.id)}>
                                <div className="relative h-[157px] w-[281px] overflow-hidden rounded-md">
                                    <div className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]" style={{ transformOrigin: 'top left' }}>
                                        <LayoutWrapper theme={template?.theme} disabled layout={template.welcomePage?.layout} imageUrl={template?.welcomePage?.imageUrl}>
                                            <WelcomePage isPreviewMode theme={template?.theme} welcomePageData={template?.welcomePage} />
                                        </LayoutWrapper>
                                    </div>
                                </div>
                                <div className="p2-new mt-2 !font-medium">{template.title}</div>
                            </div>
                        ))}
                    </div>
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
}

const Card = ({ icon, content, onClick, variant, addSoon }: CardWrapperProps) => {
    return (
        <div className={cn('border-black-300 relative flex h-[117px] w-full cursor-pointer flex-col items-center justify-center overflow-hidden rounded-lg border bg-white sm:w-[220px]', CardVariants[variant])} onClick={onClick}>
            {icon}
            <span className="p3-new text-black-800 mb-1 mt-2">{content}</span>
            {addSoon && <SoonComponent />}
        </div>
    );
};

const SoonComponent = () => {
    return (
        <div className="bg-new-pink absolute bottom-0 left-1/3 flex h-5 w-full -rotate-[30deg] items-center justify-center text-[10px] font-medium leading-none text-white">
            <span className=" ml-14 md:ml-4">Soon</span>
        </div>
    );
};

const PlusIcon = () => {
    return (
        <svg width="41" height="40" viewBox="0 0 41 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 11L20 29" stroke="#0764EB" strokeWidth="2" strokeLinecap="round" />
            <path d="M11 20H29" stroke="#0764EB" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
};

const AIIcon = () => {
    return (
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
                d="M21.8333 15.4167C21.8333 15.6598 21.7368 15.8929 21.5648 16.0648C21.3929 16.2368 21.1598 16.3333 20.9167 16.3333C19.7011 16.3333 18.5353 16.8162 17.6758 17.6758C16.8162 18.5353 16.3333 19.7011 16.3333 20.9167C16.3333 21.1598 16.2368 21.3929 16.0648 21.5648C15.8929 21.7368 15.6598 21.8333 15.4167 21.8333C15.1736 21.8333 14.9404 21.7368 14.7685 21.5648C14.5966 21.3929 14.5 21.1598 14.5 20.9167C14.5 19.7011 14.0171 18.5353 13.1576 17.6758C12.298 16.8162 11.1322 16.3333 9.91667 16.3333C9.67355 16.3333 9.44039 16.2368 9.26849 16.0648C9.09658 15.8929 9 15.6598 9 15.4167C9 15.1736 9.09658 14.9404 9.26849 14.7685C9.44039 14.5966 9.67355 14.5 9.91667 14.5C11.1322 14.5 12.298 14.0171 13.1576 13.1576C14.0171 12.298 14.5 11.1322 14.5 9.91667C14.5 9.67355 14.5966 9.44039 14.7685 9.26849C14.9404 9.09658 15.1736 9 15.4167 9C15.6598 9 15.8929 9.09658 16.0648 9.26849C16.2368 9.44039 16.3333 9.67355 16.3333 9.91667C16.3333 11.1322 16.8162 12.298 17.6758 13.1576C18.5353 14.0171 19.7011 14.5 20.9167 14.5C21.1598 14.5 21.3929 14.5966 21.5648 14.7685C21.7368 14.9404 21.8333 15.1736 21.8333 15.4167Z"
                fill="#FE3678"
            />
            <path
                d="M22.7493 27.3307C22.7493 27.5738 22.6528 27.807 22.4809 27.9789C22.309 28.1508 22.0758 28.2474 21.8327 28.2474C21.3465 28.2474 20.8801 28.4406 20.5363 28.7844C20.1925 29.1282 19.9993 29.5945 19.9993 30.0807C19.9993 30.3238 19.9028 30.557 19.7309 30.7289C19.559 30.9008 19.3258 30.9974 19.0827 30.9974C18.8396 30.9974 18.6064 30.9008 18.4345 30.7289C18.2626 30.557 18.166 30.3238 18.166 30.0807C18.166 29.5945 17.9729 29.1282 17.629 28.7844C17.2852 28.4406 16.8189 28.2474 16.3327 28.2474C16.0896 28.2474 15.8564 28.1508 15.6845 27.9789C15.5126 27.807 15.416 27.5738 15.416 27.3307C15.416 27.0876 15.5126 26.8545 15.6845 26.6825C15.8564 26.5106 16.0896 26.4141 16.3327 26.4141C16.8189 26.4141 17.2852 26.2209 17.629 25.8771C17.9729 25.5333 18.166 25.067 18.166 24.5807C18.166 24.3376 18.2626 24.1045 18.4345 23.9325C18.6064 23.7606 18.8396 23.6641 19.0827 23.6641C19.3258 23.6641 19.559 23.7606 19.7309 23.9325C19.9028 24.1045 19.9993 24.3376 19.9993 24.5807C19.9993 25.067 20.1925 25.5333 20.5363 25.8771C20.8801 26.2209 21.3465 26.4141 21.8327 26.4141C22.0758 26.4141 22.309 26.5106 22.4809 26.6825C22.6528 26.8545 22.7493 27.0876 22.7493 27.3307Z"
                fill="#FE3678"
            />
            <path
                d="M31 20.9141C31 21.1572 30.9034 21.3903 30.7315 21.5622C30.5596 21.7342 30.3264 21.8307 30.0833 21.8307C29.1109 21.8307 28.1782 22.217 27.4906 22.9047C26.803 23.5923 26.4167 24.5249 26.4167 25.4974C26.4167 25.7405 26.3201 25.9737 26.1482 26.1456C25.9763 26.3175 25.7431 26.4141 25.5 26.4141C25.2569 26.4141 25.0237 26.3175 24.8518 26.1456C24.6799 25.9737 24.5833 25.7405 24.5833 25.4974C24.5833 24.5249 24.197 23.5923 23.5094 22.9047C22.8218 22.217 21.8891 21.8307 20.9167 21.8307C20.6736 21.8307 20.4404 21.7342 20.2685 21.5622C20.0966 21.3903 20 21.1572 20 20.9141C20 20.6709 20.0966 20.4378 20.2685 20.2659C20.4404 20.094 20.6736 19.9974 20.9167 19.9974C21.8891 19.9974 22.8218 19.6111 23.5094 18.9235C24.197 18.2358 24.5833 17.3032 24.5833 16.3307C24.5833 16.0876 24.6799 15.8545 24.8518 15.6825C25.0237 15.5106 25.2569 15.4141 25.5 15.4141C25.7431 15.4141 25.9763 15.5106 26.1482 15.6825C26.3201 15.8545 26.4167 16.0876 26.4167 16.3307C26.4167 17.3032 26.803 18.2358 27.4906 18.9235C28.1782 19.6111 29.1109 19.9974 30.0833 19.9974C30.3264 19.9974 30.5596 20.094 30.7315 20.2659C30.9034 20.4378 31 20.6709 31 20.9141Z"
                fill="#FE3678"
            />
        </svg>
    );
};
