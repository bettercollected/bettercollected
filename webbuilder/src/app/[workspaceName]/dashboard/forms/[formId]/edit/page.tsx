'use client';

import { useEffect, useState } from 'react';

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
import FieldSection from '@app/views/organism/FieldSection';
import LeftDrawer from '@app/views/organism/LeftDrawer';
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from '@app/views/organism/PropertiesDrawer';
import ThankYouSlide from '@app/views/organism/ThankYouPage';
import WelcomeSlide from '@app/views/organism/WelcomePage';

export default function FormPage({ params }: { params: { formId: string } }) {
    const [layout, setLayout] = useState<'two-column-right' | 'two-column-left'>(
        'two-column-left'
    );

    const router = useRouter();
    const { formFields, setFormFields } = useFormFieldsAtom();
    const { setFormState } = useFormState();

    const { activeSlideComponent } = useActiveSlideComponent();

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
            setFormState({ ...standardForm });
            setFormFields(standardForm?.fields || []);
        }
    }, [standardForm]);

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
        <main className="flex h-screen flex-col items-center justify-start bg-black-100">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="flex max-h-body-content w-full flex-row items-center gap-10">
                <LeftDrawer layout={layout} />
                <div
                    className="relative flex h-full flex-1 flex-col items-center justify-center "
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && (
                        <FieldSection
                            slide={formFields[activeSlideComponent?.index]}
                            layout={layout}
                        />
                    )}
                    {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                    {activeSlideComponent?.id === 'welcome-page' && (
                        <WelcomeSlide layout={layout} />
                    )}

                    {activeSlideComponent?.id === 'thank-you-page' && (
                        <ThankYouSlide layout={'two-column-right'} />
                    )}
                </div>
                <div
                    id="slide-element-properties"
                    className="h-full w-[200px] self-stretch overflow-auto border-l-black-300 bg-white"
                >
                    <PropertiesDrawer layout={layout} setLayout={setLayout} />
                </div>
            </div>
        </main>
    );
}
