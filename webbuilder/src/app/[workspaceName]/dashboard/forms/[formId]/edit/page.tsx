'use client';

import { CSSProperties, useEffect, useMemo, useState } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { motion } from 'framer-motion';
import { useDebounceCallback } from 'usehooks-ts';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import AutoSaveForm from '@app/views/molecules/FormBuilder/AutoSaveForm';
import LeftDrawer from '@app/views/organism/FormBuilder/LeftDrawer';
import PropertiesDrawer from '@app/views/organism/FormBuilder/PropertiesDrawer';
import SlideBuilder from '@app/views/organism/FormBuilder/SlideBuilder';
import ThankYouSlide from '@app/views/organism/FormBuilder/ThankYouPage';
import WelcomeSlide from '@app/views/organism/FormBuilder/WelcomePage';
import Navbar from '@app/views/organism/Navbar';

export default function FormPage({ params }: { params: { formId: string } }) {
    const { formFields, setFormFields } = useFormFieldsAtom();
    const { setFormState, formState } = useFormState();

    const { activeSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const pathname = usePathname();
    const router = useRouter();

    const { navbarState, setNavbarState } = useNavbarState();

    const searchParams = useSearchParams();
    const showModal = searchParams.get('showTitle');

    const { openDialogModal } = useDialogModal();

    const { standardForm } = useStandardForm();

    const formId = params.formId;

    const getScaledDivStyles = () => {
        if (typeof window !== 'undefined') {
            const windowHeight = window.innerHeight;
            const windowWidth = window.innerWidth;
            const slideViewportWidth = windowWidth - 480;
            const slideViewportHeight = windowHeight - 192;
            const aspectRatio = 16 / 9;
            if (slideViewportWidth / aspectRatio > slideViewportHeight) {
                return {
                    height: '100vh',
                    scale: slideViewportHeight / windowHeight,
                    transformOrigin: 'top left'
                };
            }
            return {
                width: '100vw',
                scale: slideViewportWidth / windowWidth,
                transformOrigin: 'top left'
            };
        }
        return undefined;
    };
    const [scaledDivStyle, setScaledDivStyle] = useState(getScaledDivStyles());

    useEffect(() => {
        const handleResize = () => {
            setScaledDivStyle(getScaledDivStyles());
        };

        window.addEventListener('resize', handleResize, false);

        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, []);

    useEffect(() => {
        if (showModal === 'true') {
            openDialogModal('ADD_FORM_TITLE');
            router.replace(pathname);
        }
    }, [showModal]);

    useEffect(() => {
        if (standardForm.formId) {
            if (!standardForm.welcomePage || !standardForm.thankyouPage) {
                const form = { ...standardForm, ...formState };
                setFormState(form);
            } else {
                setFormState({ ...formState, ...standardForm });
            }
            setFormFields(standardForm?.fields || []);
            setNavbarState({
                ...navbarState,
                multiplePages: !!standardForm.isMultiPage
            });
        }
    }, [standardForm.formId]);

    function handleClickOutsideFieldOption(event: any) {
        var divA = document.getElementById('fields-option');
        var clickedElement = event.target as HTMLDivElement;

        if (!divA?.contains(clickedElement)) {
            setNavbarState({ ...navbarState, insertClicked: false });
        }
    }

    useEffect(() => {
        if (navbarState.insertClicked) {
            document.addEventListener('click', handleClickOutsideFieldOption);
        }

        return () => {
            document.removeEventListener('click', handleClickOutsideFieldOption);
        };
    }, [navbarState]);

    return (
        <main className="flex h-screen flex-col items-center justify-start overflow-hidden bg-white">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="flex max-h-body-content w-full flex-row items-center gap-10">
                <LeftDrawer
                    formFields={formFields}
                    activeSlideComponent={activeSlideComponent}
                />
                <motion.div
                    animate={{ x: navbarState.insertClicked ? '5%' : 0 }}
                    transition={{ ease: 'easeInOut' }}
                    className="relative max-h-full max-w-full flex-1 overflow-hidden py-14"
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    <div
                        className="aspect-video overflow-hidden"
                        style={scaledDivStyle}
                    >
                        <div className=" mx-auto h-full w-full rounded-lg  shadow-slide">
                            {activeSlideComponent?.id &&
                                activeSlideComponent?.index >= 0 && (
                                    <SlideBuilder
                                        slide={formFields[activeSlideComponent?.index]}
                                    />
                                )}
                            {!activeSlideComponent?.id && (
                                <div>Add a slide to start</div>
                            )}
                            {activeSlideComponent?.id === 'welcome-page' && (
                                <WelcomeSlide />
                            )}

                            {activeSlideComponent?.id === 'thank-you-page' && (
                                <ThankYouSlide />
                            )}
                        </div>
                    </div>
                </motion.div>
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
