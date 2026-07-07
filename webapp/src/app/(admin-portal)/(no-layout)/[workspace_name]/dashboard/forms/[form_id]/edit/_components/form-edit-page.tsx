'use client';

import { use, useEffect, useRef, useState } from 'react';

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
import { BuilderTrustStrip, TrustStripNudge } from '@app/views/molecules/form-builder/builder-trust-strip';
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

    // The slide's design size. The card is always laid out at this size and
    // scaled as a whole, so what you edit is exactly what renders at 100%.
    const CANVAS_WIDTH = 1440;
    const CANVAS_HEIGHT = 810;

    // 'fit' scales the slide into the mat; '100%' edits at true size with
    // canvas scrolling.
    const [canvasZoom, setCanvasZoom] = useState<'fit' | 'full'>('fit');
    const canvasMatRef = useRef<HTMLDivElement>(null);
    const [fitScale, setFitScale] = useState(0.5);

    // Fit is measured from the mat itself (not window arithmetic): the scaled
    // wrapper gets the same layout size as the visual card, so `m-auto`
    // centres it exactly on both axes at every viewport size.
    useEffect(() => {
        const mat = canvasMatRef.current;
        if (!mat) return;
        const compute = () => {
            const cs = getComputedStyle(mat);
            const availableWidth = mat.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
            const availableHeight = mat.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
            setFitScale(Math.min(availableWidth / CANVAS_WIDTH, availableHeight / CANVAS_HEIGHT, 1));
        };
        compute();
        const observer = new ResizeObserver(compute);
        observer.observe(mat);
        return () => observer.disconnect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const canvasScale = canvasZoom === 'full' ? 1 : fitScale;

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
        return () => {
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
                    ref={canvasMatRef}
                    className=" relative flex max-h-full max-w-full flex-1 overflow-auto bg-[#E9EEF5] px-8 py-10"
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    {/* The wrapper's layout size equals the scaled card's visual
                        size, so m-auto centring is exact; shrink-0 keeps flex from
                        compressing it at 100% (which silently broke zoom before). */}
                    <div className="m-auto shrink-0" style={{ width: CANVAS_WIDTH * canvasScale, height: CANVAS_HEIGHT * canvasScale }}>
                        {/* The sheet needs real presence on the mat — the slide's own
                            surface is near the mat's tone, so the edge comes from a
                            hairline + a soft elevation shadow, not from contrast. */}
                        <div
                            className="border-black-400 overflow-hidden rounded-lg border bg-white"
                            style={{
                                width: CANVAS_WIDTH,
                                height: CANVAS_HEIGHT,
                                transform: `scale(${canvasScale})`,
                                transformOrigin: 'top left',
                                boxShadow: '0px 1px 3px rgba(16, 24, 38, 0.06), 0px 12px 32px rgba(16, 24, 38, 0.12)'
                            }}
                        >
                            <div className="relative mx-auto h-full w-full rounded-lg">
                                {activeSlideComponent?.id && activeSlideComponent?.index >= 0 && <SlideBuilder slide={formFields[activeSlideComponent?.index]} />}
                                {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                                {activeSlideComponent?.id === 'welcome-page' && <WelcomeSlide />}

                                {activeSlideComponent?.id === 'thank-you-page' && <ThankYouSlide />}
                                {/* The trust strip, exactly where responders see it —
                                    on every page. An empty strip in plain sight is the
                                    incentive to author the trust content. */}
                                <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10">
                                    <BuilderTrustStrip />
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2" onClick={(e) => e.stopPropagation()}>
                        <TrustStripNudge />
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
