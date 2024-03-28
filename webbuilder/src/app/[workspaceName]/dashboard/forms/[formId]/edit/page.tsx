'use client';

import { useEffect } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

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
    const router = useRouter();
    const { formFields, setFormFields } = useFormFieldsAtom();
    const { setFormState, formState } = useFormState();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const { navbarState, setNavbarState } = useNavbarState();

    const searchParams = useSearchParams();
    const showModal = searchParams.get('showTitle');

    const { openDialogModal } = useDialogModal();

    const { standardForm } = useStandardForm();
    const pathname = usePathname();

    const formId = params.formId;

    useEffect(() => {
        if (showModal === 'true') {
            openDialogModal('ADD_FORM_TITLE');
            router.replace(pathname);
        }
    }, [showModal]);

    useEffect(() => {
        if (standardForm.formId) {
            setFormState({ ...standardForm, ...formState });
            setFormFields(standardForm?.fields || []);
        }
    }, [standardForm.formId]);

    function handleClickOutsideFieldOption(event: any) {
        var divA = document.getElementById('fields-option');
        var clickedElement = event.target as HTMLDivElement;

        if (!divA?.contains(clickedElement)) {
            setNavbarState({ insertClicked: false });
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
        <main className="flex h-screen flex-col items-center justify-start overflow-hidden bg-black-100">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="flex max-h-body-content w-full flex-row items-center gap-10">
                <LeftDrawer />
                <div
                    className="relative mx-10 flex h-full w-full flex-1 flex-col items-center justify-center "
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && (
                        <SlideBuilder slide={formFields[activeSlideComponent?.index]} />
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
