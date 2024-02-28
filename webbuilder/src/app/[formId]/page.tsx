'use client';

import { ReactNode, useEffect } from 'react';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';

import cn from 'classnames';
import { AnimatePresence, motion } from 'framer-motion';
import { PlusIcon } from 'lucide-react';
import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { formFieldsList } from '@app/constants/form-fields';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
import { ButtonSize, ButtonVariant } from '@app/models/enums/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useNavbarState } from '@app/store/jotai/navbar';
import Button from '@app/views/atoms/Button';
import AutoSaveForm from '@app/views/molecules/FormBuilder/AutoSaveForm';
import FieldSection from '@app/views/organism/FieldSection';
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from '@app/views/organism/PropertiesDrawer';
import ThankYouSlide from '@app/views/organism/ThankYouPage';
import WelcomeSlide from '@app/views/organism/WelcomePage';

export default function FormPage({ params }: { params: { formId: string } }) {
    const router = useRouter();
    const { addSlide, formFields, setFormFields, addField } = useFormFieldsAtom();
    const { setFormState } = useFormState();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();

    const { navbarState, setNavbarState } = useNavbarState();

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
        if (currentForm) {
            const { fields, ...state } = currentForm;
            if (currentForm?.fields) setFormFields(fields);
            setFormState(state);
        }
    }, []);

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

    const handleAddField = (field: any) => {
        if (activeSlideComponent === null) {
            toast('Add a slide to add questions');
            return;
        }

        if (activeSlideComponent?.index < 0) {
            toast('Select a slide to add questions');
            return;
        }

        const fieldId = v4();
        if (
            field.type === FieldTypes.YES_NO ||
            field.type === FieldTypes.DROP_DOWN ||
            field.type === FieldTypes.MULTIPLE_CHOICE
        ) {
            const firstChoiceId = v4();
            const secondChoiceId = v4();
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type,
                    properties: {
                        fields: [],
                        choices: [
                            {
                                id: firstChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'Yes' : ''
                            },
                            {
                                id: secondChoiceId,
                                value: field.type === FieldTypes.YES_NO ? 'No' : ''
                            }
                        ]
                    }
                },
                activeSlideComponent?.index || 0
            );
        } else {
            addField(
                {
                    id: fieldId,
                    index: formFields[activeSlideComponent!.index]?.properties?.fields
                        ?.length
                        ? formFields[activeSlideComponent!.index]?.properties?.fields
                              ?.length!
                        : 0,
                    type: field.type
                },
                activeSlideComponent?.index || 0
            );
        }
        setNavbarState({ insertClicked: false });
        window.setTimeout(function () {
            document.getElementById(`input-${fieldId}`)?.focus();
        }, 0);
    };

    return (
        <main className="flex h-screen flex-col items-center justify-start bg-black-100">
            <Navbar />
            <AutoSaveForm formId={formId} />
            <div className="flex max-h-body-content w-full flex-row items-center gap-10">
                <AnimatePresence initial={false} mode="wait">
                    {!(
                        activeSlideComponent?.id === 'welcome-page' ||
                        activeSlideComponent?.id === 'thank-you-page'
                    ) && navbarState.insertClicked ? (
                        <motion.div
                            key="field-options"
                            initial={{ opacity: 0, x: '-100%' }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: '-100%' }}
                            transition={{ duration: 0.5 }}
                            id="fields-option"
                            className=" grid h-body-content w-[240px] grid-cols-2 overflow-y-auto overflow-x-hidden bg-white 
                        "
                        >
                            {Array.isArray(formFieldsList) &&
                                formFieldsList.length &&
                                formFieldsList.map(
                                    (
                                        field: {
                                            name: string;
                                            type: FieldTypes;
                                            icon: ReactNode;
                                        },
                                        index: number
                                    ) => {
                                        return (
                                            <div
                                                onClick={() => handleAddField(field)}
                                                key={index}
                                                className="flex w-[120px] cursor-grab flex-col items-center justify-center gap-1 border-[1px] border-black-300 text-black-600"
                                            >
                                                {field.icon}
                                                <h1> {field.name}</h1>
                                            </div>
                                        );
                                    }
                                )}
                        </motion.div>
                    ) : (
                        <motion.div
                            key="field"
                            initial={{ opacity: 0, x: '-100%' }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: '-100%' }}
                            transition={{ duration: 0.5 }}
                            id="slides-preview"
                            className="flex h-body-content w-[200px] flex-col gap-5 overflow-y-auto overflow-x-hidden bg-white p-5"
                        >
                            <div className="flex w-full items-center justify-between border-b border-b-black-400 p-5">
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
                  },
                });
              }}
              icon={<PlusIcon />}
            ></Button>
          </div>
          <div className=" flex flex-1 flex-col justify-between overflow-auto">
            <div className="border-b border-b-black-400 !px-4">
              <div className="p2-new mb-1 font-medium text-black-700">
                Welcome
              </div>
              <div
                className={cn(
                  " mb-6 flex !aspect-video cursor-pointer items-center justify-center overflow-auto rounded-lg  bg-white",
                  activeSlideComponent?.id === "welcome-page" &&
                    "border border-pink-500"
                )}
                onClick={() => {
                  setActiveSlideComponent({
                    id: "welcome-page",
                    index: -10,
                  });
                }}
              >
                <WelcomeSlide disabled />
              </div>
            </div>
            <ScrollArea className="max-h-pages-container flex-1  overflow-y-auto">
              <div className="flex  w-[200px]  flex-col gap-2  px-4 py-6">
                {Array.isArray(Slides) && Slides.length ? (
                  Slides.map((slide, index) => {
                    return (
                      <div>
                        <div className="p2-new mb-1 font-medium text-black-700">
                          Page {index + 1}
                        </div>
                        <div
                          key={slide.id}
                          className={cn(
                            "relative flex items-center gap-2",
                            activeSlideComponent?.id === slide.id &&
                              "!border-pink-500"
                          )}
                        >
                          <div
                            role="button"
                            className={cn(
                              "flex !aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-lg border",
                              activeSlideComponent?.id === slide.id &&
                                "!border-pink-500"
                            )}
                            onClick={() => {
                              setActiveSlideComponent({
                                id: slide.id,
                                index,
                              });
                            }}
                          >
                            <div className={"scale-[0.25]"}>
                              <FieldSection
                                slide={slide}
                                disabled
                                isScaledDown
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <></>
                )}
              </div>
            </ScrollArea>

            <div className="border-t border-t-black-400 px-4 pt-4">
              <div className="p2-new mb-1 font-medium text-black-700">End</div>
              <div
                className={cn(
                  " mb-5 flex !aspect-video h-[85px] cursor-pointer items-center justify-center overflow-clip rounded-lg border bg-white",
                  activeSlideComponent?.id === "thank-you-page" &&
                    "border-pink-500"
                )}
                onClick={() => {
                  setActiveSlideComponent({
                    id: "thank-you-page",
                    index: -20,
                  });
                }}
              >
                <ThankYouSlide disabled />
              </div>
            </div>
          </div>
                        </motion.div>
                    )}
                </AnimatePresence>

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
