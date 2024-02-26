'use client';

import { useEffect } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import cn from 'classnames';
import { PlusIcon, Router } from 'lucide-react';
import { v4 } from 'uuid';

import { ThemeColor } from '@app/constants/theme';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormField } from '@app/models/dtos/form';
import { FieldTypes } from '@app/models/dtos/form';
import { ButtonSize, ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';

export default function HomePage() {
    const { dispatchLocalStorageFields, resetFields } = useFieldSelectorAtom();
    const Forms = JSON.parse(localStorage.getItem('Forms') || '[]');
    const handleCreateForm = () => {
        const formId = v4();
        Forms ? Forms.push({ [formId]: {} }) : [{ [formId]: {} }];
        localStorage.setItem('Forms', JSON.stringify(Forms));
        resetFields();
        router.push(`/${formId}`);
    };
    const { addSlide, formFields } = useFieldSelectorAtom();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const searchParams = useSearchParams();
    const showModal = searchParams.get('showTitle');

    const { openDialogModal } = useDialogModal();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (showModal === 'true') {
            router.push(pathname);
            openDialogModal('ADD_FORM_TITLE');
        }
    }, [showModal]);

    return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-brand-200">
            <Button size="lg" onClick={handleCreateForm}>
                Create Form
            </Button>
            <div className="flex flex-col gap-4">
                {Array.isArray(Forms) && Forms.length ? (
                    Forms.map((form: { id: [FormField] }, index) => {
                        return (
                            <div
                                className=" cursor-pointer bg-brand-300 p-2 hover:bg-brand-400"
                                key={index}
                                onClick={() => {
                                    Object.values(form)[0].length
                                        ? dispatchLocalStorageFields(
                                              Object.values(form)[0]
                                          )
                                        : dispatchLocalStorageFields([]);
                                    router.push(`/${Object.keys(form)[0]}`);
                                }}
                            >
                                <h1>Form with id {Object.keys(form)[0]}</h1>
                            </div>
                        );
                    })
                ) : (
                    <>No forms to display</>
                )}
            </div>
        </div>
    );
}
