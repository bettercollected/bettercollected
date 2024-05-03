'use client';

import { useEffect, useState } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { motion } from 'framer-motion';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { deepCopy } from '@app/utils/objectUtils';
import AutoSaveForm from '@app/views/molecules/FormBuilder/AutoSaveForm';
import LeftDrawer from '@app/views/organism/FormBuilder/LeftDrawer';
import PropertiesDrawer from '@app/views/organism/FormBuilder/PropertiesDrawer';
import SlideBuilder from '@app/views/organism/FormBuilder/SlideBuilder';
import ThankYouSlide from '@app/views/organism/FormBuilder/ThankYouPage';
import WelcomeSlide from '@app/views/organism/FormBuilder/WelcomePage';
import Navbar from '@app/views/organism/Navbar';

export default function FormPage({ params }: { params: { form_id: string } }) {
    const { formFields, setFormFields } = useFormFieldsAtom();
    const { setFormState, formState } = useFormState();

    const { activeSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const pathname = usePathname();
    const router = useRouter();

    const { navbarState, setNavbarState } = useNavbarState();

    const searchParams = useSearchParams();
    const showModal = searchParams?.get('showTitle');

    const { openDialogModal } = useDialogModal();

    const standardForm: any = useAppSelector(selectForm);

    const formId = params.form_id;

    const getScaledDivStyles = () => {
        if (typeof window !== 'undefined') {
            const windowHeight = window.innerHeight;
            const windowWidth = window.innerWidth;
            const slideViewportWidth = windowWidth - 520;
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

    const getScaledDivWidth = () => {
        const styles = getScaledDivStyles();
        if (styles?.width) {
            return window.innerWidth - 520;
        }
        return ((window?.innerHeight - 192) * 16) / 9;
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
            if (pathname) router.replace(pathname);
        }
    }, [showModal]);

    useEffect(() => {
        if (standardForm.formId) {
            if (!standardForm.welcomePage || !standardForm.thankyouPage) {
                const form = { ...standardForm, ...formState };
                setFormState(form);
            } else {
                const copiedThankyouPage = deepCopy(standardForm?.thankyouPage || formState.thankyouPage);
                const copiedWelcomePage = deepCopy(standardForm?.welcomePage || formState.welcomePage);
                const form = {
                    ...formState,
                    title: standardForm.title,
                    thankyouPage: copiedThankyouPage,
                    welcomePage: copiedWelcomePage
                };
                setFormState(form);
            }
            const deepCopiedFormFields = deepCopy(standardForm?.fields || []);
            setFormFields(deepCopiedFormFields);
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

    // useEffect(() => {
    //     if (navbarState.insertClicked) {
    //         document.addEventListener('click', handleClickOutsideFieldOption);
    //     }

    //     return () => {
    //         document.removeEventListener('click', handleClickOutsideFieldOption);
    //     };
    // }, [navbarState]);

    return (
        <main className=" flex h-screen flex-col items-center justify-start overflow-hidden bg-white">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="max-h-body-content  flex w-full flex-row items-center gap-10">
                <LeftDrawer formFields={formFields} activeSlideComponent={activeSlideComponent} />
                <div
                    className=" relative flex max-h-full max-w-full flex-1 justify-center overflow-x-hidden px-5 py-14"
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    <div
                        style={{
                            width: getScaledDivWidth()
                        }}
                    >
                        <div className="!shadow-slide aspect-video overflow-hidden" style={scaledDivStyle}>
                            <div className="   mx-auto h-full w-full  rounded-lg">
                                {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && <SlideBuilder slide={formFields[activeSlideComponent?.index]} />}
                                {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                                {activeSlideComponent?.id === 'welcome-page' && <WelcomeSlide />}

                                {activeSlideComponent?.id === 'thank-you-page' && <ThankYouSlide />}
                            </div>
                        </div>
                    </div>
                </div>
                <div id="slide-element-properties" className="border-l-black-300 h-full w-[200px] self-stretch overflow-auto bg-white">
                    <PropertiesDrawer />
                </div>
            </div>
        </main>
    );
}
