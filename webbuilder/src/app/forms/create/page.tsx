'use client';

import React from 'react';

import Image from 'next/image';
import { useRouter } from 'next/navigation';

import cn from 'classnames';
import { ChevronLeft, Download, Plus, Sparkles } from 'lucide-react';
import { URL } from 'url';
import { v4 } from 'uuid';

import useFormBuilderAtom from '@app/store/jotai/fieldSelector';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

const CardVariants = {
    blue: 'text-blue-500 hover:bg-blue-100 hover:border-blue-100',
    orange: 'text-orange-500 hover:bg-orange-100 hover:border-orange-100',
    pink: 'text-pink-500 hover:bg-pink-100 hover:border-pink-100'
};

const templates = [
    {
        title: 'Contact Form',
        imageUrl:
            'https://images.unsplash.com/photo-1572431672794-6c27cd42af45?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDF8NnNNVmpUTFNrZVF8fGVufDB8fHx8fA%3D%3D'
    },
    {
        title: 'Party Invitation',
        imageUrl:
            'https://images.unsplash.com/photo-1693491012999-09a3764eab33?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDJ8NnNNVmpUTFNrZVF8fGVufDB8fHx8fA%3D%3D'
    },
    {
        title: 'RSVP Form',
        imageUrl:
            'https://images.unsplash.com/photo-1489589947464-ac72e1abd198?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDR8NnNNVmpUTFNrZVF8fGVufDB8fHx8fA%3D%3D'
    },
    {
        title: 'Interview Form',
        imageUrl:
            'https://images.unsplash.com/photo-1555396273-755660f19034?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDV8NnNNVmpUTFNrZVF8fGVufDB8fHx8fA%3D%3D'
    },
    {
        title: 'Sign In Form',
        imageUrl:
            'https://images.unsplash.com/photo-1505516580118-8502b2e37c44?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDd8NnNNVmpUTFNrZVF8fGVufDB8fHx8fA%3D%3D'
    },
    {
        title: 'Order Form',
        imageUrl:
            'https://images.unsplash.com/photo-1529697216570-f48ef8f6b2dd?w=500&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDEzfDZzTVZqVExTa2VRfHxlbnwwfHx8fHw%3D'
    },
    {
        title: 'Party Invitation',
        imageUrl:
            'https://images.unsplash.com/photo-1490395930356-7e64acf16e23?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDIxfDZzTVZqVExTa2VRfHxlbnwwfHx8fHw%3D'
    },
    {
        title: 'User Onboarding Form',
        imageUrl:
            'https://images.unsplash.com/photo-1486990530088-cb9ce1a840bf?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHx0b3BpYy1mZWVkfDI2fDZzTVZqVExTa2VRfHxlbnwwfHx8fHw%3D'
    }
];

const Forms = JSON.parse(localStorage.getItem('Forms') || '[]');

export default function CreateFormPage() {
    const { resetFields } = useFormBuilderAtom();
    const handleCreateForm = () => {
        const formId = v4();
        Forms ? Forms.push({ [formId]: {} }) : [{ [formId]: {} }];
        localStorage.setItem('Forms', JSON.stringify(Forms));
        resetFields();
        router.push(`/${formId}`);
    };

    const router = useRouter();
    return (
        <div className="min-h-screen bg-white">
            <div
                id="navbar"
                className="flex h-16 w-full items-center justify-start border-b-[1px] border-b-black-300 !bg-white p-4"
            >
                <div className={'mr-4 rounded-lg px-4 py-[6px] shadow'}>
                    <BetterCollectedSmallLogo />
                </div>
                <div className="flex gap-2 text-black-700">
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
                <div className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
                    {templates.map((template) => (
                        <div
                            className="flex cursor-pointer flex-col"
                            key={template.imageUrl}
                        >
                            <div className="relative !aspect-video overflow-hidden rounded-md">
                                <Image
                                    alt={template.title}
                                    src={template.imageUrl}
                                    fill
                                    sizes="100%"
                                    style={{ objectFit: 'cover' }}
                                />
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
