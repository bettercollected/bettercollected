'use client';

import React from 'react';

import { useRouter } from 'next/navigation';

import cn from 'classnames';
import { ChevronLeft, Download, Plus, Sparkles } from 'lucide-react';

import environments from '@app/configs/environments';
import { defaultForm } from '@app/constants/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import useWorkspace from '@app/store/jotai/workspace';
import { useCreateV2FormMutation } from '@app/store/redux/formApi';
import {
    useCreateFormFromTemplateMutation,
    useGetTemplatesQuery
} from '@app/store/redux/templateApi';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';
import WelcomePage from '@app/views/organism/Form/WelcomePage';
import LayoutWrapper from '@app/views/organism/Layout/LayoutWrapper';


const CardVariants = {
    blue: 'text-blue-500 hover:bg-blue-100 hover:border-blue-100',
    orange: 'text-orange-500 hover:bg-orange-100 hover:border-orange-100',
    pink: 'text-pink-500 hover:bg-pink-100 hover:border-pink-100'
};

export default function CreateFormPage() {
    const [createV2Form] = useCreateV2FormMutation();
    const { resetFields } = useFormFieldsAtom();
    const { workspace } = useWorkspace();
    const router = useRouter();

    const { data: templates } = useGetTemplatesQuery({ v2: true });

    const [createFormFrmTemplate] = useCreateFormFromTemplateMutation();

    const handleCreateForm = async () => {
        resetFields();
        const formBody = { ...defaultForm, builderVersion: 'v2' };
        const formData = new FormData();
        formData.append('form_body', JSON.stringify(formBody));
        const apiRequestBody: any = { workspaceId: workspace.id, body: formData };
        const response: any = await createV2Form(apiRequestBody);
        if (response?.data) {
            router.replace(
                `/${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit?showTitle=true`
            );
        }
    };

    const createFormFromTemplate = async (templateId: string) => {
        const response: any = await createFormFrmTemplate({
            workspace_id: workspace.id,
            template_id: templateId
        });
        const editFormUrl = `/${workspace.workspaceName}/dashboard/forms/${response?.data?.formId}/edit?showTitle=true`;
        router.push(editFormUrl);
    };

    return (
        <div className="min-h-screen bg-white">
            <div
                id="navbar"
                className="flex h-16 w-full items-center justify-start border-b-[1px] border-b-black-300 !bg-white p-4"
            >
                <div className={'mr-4 rounded-lg px-4 py-[6px] shadow'}>
                    <BetterCollectedSmallLogo
                        onClick={() => {
                            router.push(
                                environments.NEXT_PUBLIC_HTTP_SCHEME +
                                    '://' +
                                    environments.NEXT_PUBLIC_DASHBOARD_DOMAIN +
                                    '/' +
                                    workspace.workspaceName +
                                    '/dashboard'
                            );
                        }}
                    />
                </div>
                <div
                    className="flex cursor-pointer gap-2 text-black-700"
                    onClick={() => {
                        router.back();
                    }}
                >
                    <ChevronLeft />
                    Back
                </div>
            </div>
            <div className="m-auto flex max-w-[1200px] flex-col px-5 md:px-10">
                <div className="h3-new mb-4 mt-6 text-black-800">New Form</div>
                <div className="flex flex-wrap gap-6">
                    <Card
                        variant={'blue'}
                        icon={<Plus size={24} className="text-blue-500" />}
                        content={'Create New Form'}
                        onClick={handleCreateForm}
                    />
                    <Card
                        variant={'orange'}
                        icon={<Download size={24} className="text-orange-500" />}
                        content={'Import Form'}
                        onClick={() => {}}
                    />
                    <Card
                        variant={'pink'}
                        icon={<Sparkles size={24} className="text-pink-500" />}
                        content={'Start with AI'}
                        onClick={() => {}}
                    />
                </div>

                <div className="h3-new mb-4 mt-12 text-black-800">Templates</div>
                <div className="flex w-full flex-row flex-wrap gap-x-6 gap-y-10 ">
                    {templates?.map((template) => (
                        <div
                            className="flex cursor-pointer flex-col rounded-lg border border-transparent p-1 hover:border-pink-500"
                            key={template?.id}
                            onClick={() => createFormFromTemplate(template.id)}
                        >
                            <div className="relative h-[157px] w-[281px] overflow-hidden rounded-md">
                                <div
                                    className="pointer-events-none h-[810px] w-[1440px] scale-[0.195]"
                                    style={{ transformOrigin: 'top left' }}
                                >
                                    <LayoutWrapper
                                        theme={template?.theme}
                                        disabled
                                        layout={template.welcomePage?.layout}
                                        imageUrl={template?.welcomePage?.imageUrl}
                                    >
                                        <WelcomePage
                                            isPreviewMode
                                            welcomePageData={template?.welcomePage}
                                        />
                                    </LayoutWrapper>
                                </div>
                            </div>
                            <div className="p2-new mt-2 !font-medium">
                                {template.title}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

interface CardWrapperProps {
    icon: React.ReactNode;
    content: React.ReactNode;
    onClick: React.MouseEventHandler<HTMLDivElement>;
    variant: 'blue' | 'orange' | 'pink';
}

const Card = ({ icon, content, onClick, variant }: CardWrapperProps) => {
    return (
        <div
            className={cn(
                'flex h-[117px] w-full cursor-pointer flex-col items-center justify-center rounded-md border border-black-300 bg-white sm:w-[220px]',
                CardVariants[variant]
            )}
            onClick={onClick}
        >
            {icon}
            <span className="p3-new mt-2 text-black-800">{content}</span>
        </div>
    );
};
