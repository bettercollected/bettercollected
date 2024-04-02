'use client';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import useGetPageAttributes from '@app/lib/hooks/useGetPageAttributes';
import { FormSlideLayout } from '@app/models/enums/form';
import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';
import {
    useActiveFieldComponent,
    useActiveSlideComponent,
    useActiveThankYouPageComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import { SlideLayoutNoImageLeftAlign } from '@app/views/atoms/Icons/SlideLayoutNoImageLeftAlign';

import SlideLayoutBackgroundImage from '../../atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '../../atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '../../atoms/Icons/SlideLayoutNoImage';
import SlideLayoutRightImage from '../../atoms/Icons/SlideLayoutRightImage';

export default function PagePropertiesTab({}: {}) {
    const {
        formFields,
        updateShowQuestionNumbers,
        activeSlide,
        updateSlideLayout,
        updateSlideImage
    } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const {
        formState,
        setWelcomePageButtonText,
        setThankYouPageDescription,
        setThankYouPageButtonText,
        setThankYouPageButtonLink,
        updateThankYouPageLayout,
        updateWelcomePageLayout,
        setFormDescription
    } = useFormState();

    const { openDialogModal } = useDialogModal();
    function getPageIndex() {
        if (activeSlideComponent?.id === 'welcome-page') return -10;
        else if (activeSlideComponent?.id === 'thank-you-page') return -20;
        else return activeSlide?.index;
    }
    const { layout, imageUrl } = useGetPageAttributes(getPageIndex() ?? -10);

    const { updateFieldRequired } = useFormFieldsAtom();

    const getLayoutList = () => {
        if (
            layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND ||
            layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
        ) {
            return [
                {
                    style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN,
                    Icon: SlideLayoutNoImageLeftAlign
                },
                {
                    style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                    Icon: SlideLayoutNoImage
                }
            ];
        } else
            return [
                {
                    style: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                    Icon: SlideLayoutRightImage
                },
                {
                    style: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT,
                    Icon: SlideLayoutLeftImage
                },
                {
                    style: FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND,
                    Icon: SlideLayoutBackgroundImage
                }
            ];
    };

    // Function to handle layout update for a specific slide
    const handleSlideLayoutChange = (slideId?: string, newLayout?: FormSlideLayout) => {
        if (newLayout) {
            if (slideId === 'welcome-page') {
                updateWelcomePageLayout(newLayout);
            } else if (slideId === 'thank-you-page') {
                updateThankYouPageLayout(newLayout);
            } else {
                updateSlideLayout(newLayout);
            }
        }
    };

    return (
        <>
            {
                <>
                    <div className="p2-new mb-4 mt-6 px-4 !font-medium text-black-700">
                        Layout
                    </div>
                    <div className="grid grid-cols-2 gap-2 border-b px-4 pb-6">
                        {getLayoutList().map(
                            (item: { style: FormSlideLayout; Icon: any }) => (
                                <div
                                    key={item.style}
                                    className={cn(
                                        'flex h-[50px] w-20 cursor-pointer items-center justify-center rounded-xl border-[1px] p-2 hover:bg-gray-200',

                                        layout && layout === item.style
                                            ? 'border-pink-500 ring-offset-1'
                                            : 'border-gray-200'
                                    )}
                                    onClick={() =>
                                        handleSlideLayoutChange(
                                            activeSlideComponent?.id,
                                            item.style
                                        )
                                    }
                                >
                                    {item.Icon && <item.Icon />}
                                </div>
                            )
                        )}
                    </div>
                </>
            }
            <div className="p2-new mb-4 mt-6 px-4 !font-medium text-black-700">
                Settings
            </div>
            <div className="flex w-full items-center justify-between border-b px-4 pb-4">
                {activeSlideComponent?.id === 'welcome-page' ||
                activeSlideComponent?.id === 'thank-you-page' ? (
                    <div className="flex w-full flex-col gap-4">
                        <div className="flex flex-row justify-between">
                            <div className="text-xs text-black-700">Description</div>
                            <Switch
                                checked={
                                    activeSlideComponent?.id === 'welcome-page'
                                        ? formState?.welcomePage?.description !==
                                              undefined &&
                                          formState?.welcomePage?.description !== null
                                        : formState.thankyouPage &&
                                          formState.thankyouPage[
                                              activeThankYouPageComponent?.index || 0
                                          ].message !== undefined
                                }
                                onCheckedChange={(checked) => {
                                    activeSlideComponent?.id === 'welcome-page'
                                        ? setFormDescription(checked ? '' : undefined)
                                        : setThankYouPageDescription(
                                              activeThankYouPageComponent?.index || 0,
                                              checked ? '' : undefined
                                          );
                                }}
                            />
                        </div>
                        {activeSlideComponent?.id === 'thank-you-page' ? (
                            <div className="flex flex-col gap-3">
                                <div className="flex flex-row justify-between">
                                    <div className="text-xs text-black-700">Button</div>
                                    <Switch
                                        checked={
                                            formState.thankyouPage &&
                                            formState.thankyouPage[
                                                activeThankYouPageComponent?.index || 0
                                            ].buttonText !== undefined
                                        }
                                        onCheckedChange={(checked) => {
                                            setThankYouPageButtonText(
                                                activeThankYouPageComponent?.index || 0,
                                                checked ? '' : undefined
                                            );
                                        }}
                                    />
                                </div>
                                {formState.thankyouPage &&
                                    formState.thankyouPage[
                                        activeThankYouPageComponent?.index || 0
                                    ].buttonText !== undefined && (
                                        <>
                                            <input
                                                type="text"
                                                placeholder="Try bettercollected"
                                                value={
                                                    formState.thankyouPage &&
                                                    formState.thankyouPage[
                                                        activeThankYouPageComponent?.index ||
                                                            0
                                                    ].buttonText
                                                }
                                                onChange={(e: any) =>
                                                    setThankYouPageButtonText(
                                                        activeThankYouPageComponent?.index ||
                                                            0,
                                                        e.target.value
                                                    )
                                                }
                                                className="borer-[1px] rounded-lg border-black-300 p-2 text-xs focus:border-black-300 active:border-black-300"
                                            />
                                            <div className="flex flex-row justify-between">
                                                <div className="text-xs text-black-700">
                                                    Button Link
                                                </div>
                                                <Switch
                                                    checked={
                                                        formState.thankyouPage &&
                                                        formState.thankyouPage[
                                                            activeThankYouPageComponent?.index ||
                                                                0
                                                        ].buttonLink !== undefined
                                                    }
                                                    onCheckedChange={(checked) => {
                                                        setThankYouPageButtonLink(
                                                            activeThankYouPageComponent?.index ||
                                                                0,
                                                            checked ? '' : undefined
                                                        );
                                                    }}
                                                />
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="Enter your link here"
                                                value={
                                                    formState.thankyouPage &&
                                                    formState.thankyouPage[
                                                        activeThankYouPageComponent?.index ||
                                                            0
                                                    ].buttonLink
                                                }
                                                onChange={(e: any) =>
                                                    setThankYouPageButtonLink(
                                                        activeThankYouPageComponent?.index ||
                                                            0,
                                                        e.target.value
                                                    )
                                                }
                                                className="borer-[1px] rounded-lg border-black-300 p-2 text-xs focus:border-black-300 active:border-black-300"
                                            />
                                        </>
                                    )}
                            </div>
                        ) : (
                            <div className="flex flex-col gap-3">
                                <div className="text-xs text-black-700">Button</div>
                                <input
                                    type="text"
                                    placeholder="Start"
                                    value={formState.welcomePage?.buttonText}
                                    onChange={(e: any) =>
                                        setWelcomePageButtonText(e.target.value)
                                    }
                                    className="borer-[1px] rounded-lg border-black-300 p-2 text-xs focus:border-black-300 active:border-black-300"
                                />
                            </div>
                        )}
                    </div>
                ) : (
                    <>
                        {/* <div className="text-xs text-black-700">Question Numbers</div>
                        <Switch
                            checked={
                                activeSlide?.properties?.showQuestionNumbers || false
                            }
                            onCheckedChange={(checked) => {
                                updateShowQuestionNumbers(activeSlide!.index, checked);
                            }}
                        /> */}
                    </>
                )}
            </div>
            {activeSlideComponent?.id === 'welcome-page' ||
            activeSlideComponent?.id === 'thank-you-page' ? (
                <></>
            ) : (
                <>
                    <div className="p2-new mb-6 mt-6 px-4 !font-medium text-black-700">
                        Used Fields
                    </div>
                    <div className="mb-4 flex flex-col gap-6 px-4">
                        {activeSlideComponent?.index !== undefined &&
                            formFields[
                                activeSlideComponent.index
                            ]?.properties?.fields?.map((field) => {
                                return (
                                    <div
                                        key={field.id}
                                        className="flex items-center justify-between gap-2 text-xs text-black-700"
                                    >
                                        <div
                                            className="cursor-pointer truncate text-xs "
                                            // onClick={() => {
                                            //     setActiveFieldComponent({
                                            //         id: field.id,
                                            //         index: field.index
                                            //     });

                                            //     const fieldDiv =
                                            //         document.getElementById(field.id);
                                            //     console.log(
                                            //         document.getElementById(
                                            //             'scroll-div'
                                            //         )?.scrollHeight
                                            //     );
                                            // }}
                                        >
                                            {extractTextfromJSON(field)}
                                        </div>
                                        <svg
                                            width="20"
                                            height="20"
                                            viewBox="0 0 20 20"
                                            fill="none"
                                            onClick={() => {
                                                updateFieldRequired(
                                                    field.index,
                                                    activeSlideComponent.index,
                                                    !field?.validations?.required
                                                );
                                            }}
                                            className={cn(
                                                'cursor-pointer',
                                                field?.validations?.required
                                                    ? 'text-black-900'
                                                    : 'text-[#DBDBDB]'
                                            )}
                                            xmlns="http://www.w3.org/2000/svg"
                                        >
                                            <path
                                                d="M6 12.2695L14.0001 7.72927"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                            />
                                            <path
                                                d="M6 7.73047L14.0001 12.2707"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                            />
                                            <path
                                                d="M10 14L10 6"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                            />
                                        </svg>
                                    </div>
                                );
                            })}
                        {activeSlideComponent?.index !== undefined &&
                            (!formFields[activeSlideComponent.index]?.properties
                                ?.fields ||
                                !formFields[activeSlideComponent.index]?.properties
                                    ?.fields?.length) && (
                                <div className="text-black-700z text-xs">
                                    No form fields in this page. Add elements to this
                                    page will be shown here
                                </div>
                            )}
                    </div>
                </>
            )}
        </>
    );
}
