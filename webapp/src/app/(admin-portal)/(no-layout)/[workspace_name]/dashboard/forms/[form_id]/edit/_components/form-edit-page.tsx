'use client';

import { use, useEffect, useState } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom, { initialFieldsState } from '@app/store/jotai/field-selectors';
import { initialFormState, useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import { deepCopy } from '@app/utils/object-utils';
import AutoSaveForm from '@app/views/molecules/form-builder/audo-save-form';
import LeftDrawer from '@app/views/organism/form-builder/left-drawer';
import PropertiesDrawer from '@app/views/organism/form-builder/properties-drawer';
import SlideBuilder from '@app/views/organism/form-builder/slide-builder';
import ThankYouSlide from '@app/views/organism/form-builder/thankyou-page';
import WelcomeSlide from '@app/views/organism/form-builder/welcome-page';
import Navbar from '@app/views/organism/navbar';
import FloatingPopOverButton from '@Components/sidebar/floating-pop-over-button';
import HelpMenuComponent from '@Components/sidebar/help-menu-component';
import HelpMenuItem from '@Components/sidebar/help-menu-item';

export default function FormEditPage(props: { params: Promise<{ form_id: string }> }) {
    const params = use(props.params);
    const { formFields, setFormFields, initFormFields } = useFormFieldsAtom();
    const { setFormState, formState, } = useFormState();

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
            return window.innerWidth - 620;
        }
        return ((window?.innerHeight - 192) * 16) / 9;
    };

    const [scaledDivStyle, setScaledDivStyle] = useState(getScaledDivStyles());
    // 'fit' scales the 1440px slide into the viewport (~0.57 — 24px text edits
    // at ~14px); '100%' edits at true size with canvas scrolling.
    const [canvasZoom, setCanvasZoom] = useState<'fit' | 'full'>('fit');

    // Esc deselects the active field — the drawer otherwise traps you until
    // you discover that clicking empty canvas goes back.
    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setActiveFieldComponent(null);
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const handleResize = () => {
            setScaledDivStyle(getScaledDivStyles());
        };

        window.addEventListener('resize', handleResize, false);

        return () => {
            window.removeEventListener('resize', handleResize);
            setFormState({ ...initialFormState });
            // initialFieldsState is an ARRAY — `{ ...array }` turns it into an
            // object and poisons the atom for the next editor mount (anything
            // calling formFields.some/map then crashes). Deep-copy keeps the
            // module-level template safe from later in-place mutations too.
            setFormFields(deepCopy(initialFieldsState));
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
                    welcomePage: copiedWelcomePage,
                    hiddenFields: standardForm.hiddenFields
                };
                setFormState(form);
            }
            const deepCopiedFormFields = deepCopy(standardForm?.fields || []);
            initFormFields(deepCopiedFormFields);
            setNavbarState({
                ...navbarState,
                multiplePages: !!standardForm.isMultiPage
            });
        }
    }, [standardForm.formId]);

    return (
        <main className=" flex h-screen flex-col items-center justify-start overflow-hidden bg-white">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="max-h-body-content  flex w-full flex-row items-center">
                <LeftDrawer formFields={formFields} activeSlideComponent={activeSlideComponent} />
                {/* Neutral workspace mat behind the canvas, so the slide being edited
                    reads as the artefact and separates from the tool's chrome. */}
                <div
                    className=" relative flex max-h-full max-w-full flex-1 overflow-auto bg-[#E9EEF5] px-5 py-14"
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    <div
                        // shrink-0: this is a flex child — without it, flex-shrink
                        // compresses the 1440px true-size canvas back into the
                        // container and "100%" zoom silently does nothing.
                        className="m-auto shrink-0"
                        style={{
                            width: canvasZoom === 'full' ? 1440 : getScaledDivWidth()
                        }}
                    >
                        {/* The sheet needs real presence on the mat — the slide's own
                            surface is near the mat's tone, so the edge comes from a
                            hairline + a soft elevation shadow, not from contrast. */}
                        <div
                            className="border-black-400 aspect-video overflow-hidden rounded-lg border bg-white"
                            style={{ boxShadow: '0px 1px 3px rgba(16, 24, 38, 0.06), 0px 12px 32px rgba(16, 24, 38, 0.12)', ...(canvasZoom === 'full' ? {} : scaledDivStyle) }}
                        >
                            <div className="   mx-auto h-full w-full  rounded-lg">
                                {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && <SlideBuilder slide={formFields[activeSlideComponent?.index]} />}
                                {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                                {activeSlideComponent?.id === 'welcome-page' && <WelcomeSlide />}

                                {activeSlideComponent?.id === 'thank-you-page' && <ThankYouSlide />}
                            </div>
                        </div>
                    </div>
                    <div className="border-black-300 absolute bottom-4 right-4 z-10 flex overflow-hidden rounded-lg border bg-white text-xs font-medium shadow-sm" onClick={(e) => e.stopPropagation()}>
                        <button className={canvasZoom === 'fit' ? 'bg-black-100 text-black-900 px-3 py-1.5 font-semibold' : 'text-black-600 hover:text-black-900 px-3 py-1.5'} onClick={() => setCanvasZoom('fit')}>
                            Fit
                        </button>
                        <button className={canvasZoom === 'full' ? 'bg-black-100 text-black-900 px-3 py-1.5 font-semibold' : 'text-black-600 hover:text-black-900 px-3 py-1.5'} onClick={() => setCanvasZoom('full')}>
                            100%
                        </button>
                    </div>
                </div>
                <div id="slide-element-properties" className="border-l-black-300 h-full w-[300px] self-stretch overflow-auto bg-white">
                    <PropertiesDrawer />
                </div>
                <FloatingPopOverButton content={<HelpMenuComponent />}>
                    <HelpMenuItem />
                </FloatingPopOverButton>
            </div>
        </main>
    );
}
