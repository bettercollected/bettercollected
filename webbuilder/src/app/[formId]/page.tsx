'use client';

import { useEffect } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { current } from '@reduxjs/toolkit';
import cn from 'classnames';
import { log } from 'console';
import { PlusIcon } from 'lucide-react';
import { v4 } from 'uuid';

import { ThemeColor } from '@app/constants/theme';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
import { ButtonSize, ButtonVariant } from '@app/models/enums/button';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import Button from '@app/views/atoms/Button';
import AutoSaveForm from '@app/views/molecules/FormBuilder/AutoSaveForm';
import FieldSection from '@app/views/organism/FieldSection';
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from '@app/views/organism/PropertiesDrawer';
import ThankYouSlide from '@app/views/organism/ThankYouPage';
import WelcomeSlide from '@app/views/organism/WelcomePage';

export default function FormPage({ params }: { params: { formId: string } }) {
    const router = useRouter();
    const { addSlide, formFields, setFormFields, resetFields } = useFormFieldsAtom();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const Slides = formFields;

    const searchParams = useSearchParams();
    const showModal = searchParams.get('showTitle');

    const { openDialogModal } = useDialogModal();
    const pathname = usePathname();

    const formId = params.formId;
    useEffect(() => {
        if (showModal === 'true') {
            openDialogModal('ADD_FORM_TITLE');
            router.replace(pathname);
        }
    }, [showModal]);

    useEffect(() => {
        const forms = JSON.parse(localStorage.getItem('forms') || '{}');
        const currentForm = forms[formId];
        if (currentForm?.fields) setFormFields(currentForm.fields);
    }, []);

    return (
        <main className="flex h-screen flex-col items-center justify-start bg-black-100">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="flex max-h-body-content  w-full flex-row items-center gap-10">
                <div
                    id="slides-preview"
                    className="flex h-body-content w-[200px] flex-col gap-5 overflow-x-hidden overflow-y-scroll bg-white p-5"
                >
                    <div className="flex w-full items-center justify-between">
                        <span className="h4-new font-medium text-black-700">Pages</span>
                        <Button
                            variant={ButtonVariant.Secondary}
                            className="!p-2"
                            size={ButtonSize.Small}
                            onClick={() => {
                                const fieldId = v4();
                                addSlide({
                                    id: fieldId,
                                    index: formFields.length,
                                    type: FieldTypes.SLIDE,
                                    properties: {
                                        fields: [],
                                        theme: {
                                            title: 'Default',
                                            primary: ThemeColor.primary,
                                            secondary: ThemeColor.secondary,
                                            tertiary: ThemeColor.tertiary,
                                            accent: ThemeColor.accent
                                        }
                                    }
                                });
                            }}
                            icon={<PlusIcon />}
                        ></Button>
                    </div>
                    <div
                        className={cn(
                            'ml-3 flex !aspect-video !h-[85px] cursor-pointer items-center justify-center overflow-auto rounded-lg border bg-white',
                            activeSlideComponent?.id === 'welcome-page' &&
                                'border-pink-500'
                        )}
                        onClick={() => {
                            setActiveSlideComponent({
                                id: 'welcome-page',
                                index: -10
                            });
                        }}
                    >
                        <WelcomeSlide disabled />
                    </div>
                    {Array.isArray(Slides) && Slides.length ? (
                        Slides.map((slide, index) => {
                            return (
                                <div
                                    key={slide.id}
                                    className={cn(
                                        'relative flex items-center gap-2',
                                        activeSlideComponent?.id === slide.id &&
                                            '!border-pink-500'
                                    )}
                                >
                                    <span
                                        className={cn(
                                            'absolute -left-2',
                                            activeSlideComponent?.id === slide.id
                                                ? 'text-pink-500'
                                                : 'text-black-700'
                                        )}
                                    >
                                        {index + 1}
                                    </span>
                                    <div
                                        role="button"
                                        className={cn(
                                            'ml-3 flex !aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-lg border',
                                            activeSlideComponent?.id === slide.id &&
                                                '!border-pink-500'
                                        )}
                                        onClick={() => {
                                            setActiveSlideComponent({
                                                id: slide.id,
                                                index
                                            });
                                        }}
                                    >
                                        <div className={'scale-[0.25]'}>
                                            <FieldSection
                                                slide={slide}
                                                disabled
                                                isScaledDown
                                            />
                                        </div>
                                    </div>
                                </div>
                            );
                        })
                    ) : (
                        <></>
                    )}
                    <div
                        className={cn(
                            'ml-3 flex !aspect-video h-[85px] cursor-pointer items-center justify-center overflow-clip rounded-lg border bg-white',
                            activeSlideComponent?.id === 'thank-you-page' &&
                                'border-pink-500'
                        )}
                        onClick={() => {
                            setActiveSlideComponent({
                                id: 'thank-you-page',
                                index: -20
                            });
                        }}
                    >
                        <ThankYouSlide disabled />
                    </div>
                </div>
                <div
                    className="relative flex h-full flex-1 flex-col items-center justify-center "
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && (
                        <FieldSection slide={formFields[activeSlideComponent?.index]} />
                    )}
                    {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                    {activeSlideComponent?.id === 'welcome-page' && <WelcomeSlide />}

                    {activeSlideComponent?.id === 'thank-you-page' && <ThankYouSlide />}
                </div>
                <div
                    id="slide-element-properties"
                    className="h-full w-[200px] self-stretch overflow-auto border-l-black-300 bg-white"
                >
                    <PropertiesDrawer />
                </div>
            </div>
        </main>
    );
}
