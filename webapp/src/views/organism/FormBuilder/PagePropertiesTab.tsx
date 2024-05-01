'use client';

import useGetPageAttributes from '@app/lib/hooks/useGetPageAttributes';
import { FormSlideLayout } from '@app/models/enums/form';
import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';
import RequiredIcon from '@app/views/atoms/Icons/Required';
import { SlideLayoutNoImageLeftAlign } from '@app/views/atoms/Icons/SlideLayoutNoImageLeftAlign';

import { IsValidString } from '@app/utils/stringUtils';
import SlideLayoutBackgroundImage from '../../atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '../../atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '../../atoms/Icons/SlideLayoutNoImage';
import SlideLayoutRightImage from '../../atoms/Icons/SlideLayoutRightImage';

export default function PagePropertiesTab({}: {}) {
    const { formFields, activeSlide, updateSlideLayout, updateSlideImage } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const { formState, setWelcomePageButtonText, setThankYouPageDescription, setThankYouPageButtonText, setThankYouPageButtonLink, updateThankYouPageLayout, updateWelcomePageLayout, setFormDescription } = useFormState();

    function getPageIndex() {
        if (activeSlideComponent?.id === 'welcome-page') return -10;
        else if (activeSlideComponent?.id === 'thank-you-page') return -20;
        else return activeSlide?.index;
    }
    const { layout } = useGetPageAttributes(getPageIndex() ?? -10);

    const { updateFieldRequired } = useFormFieldsAtom();

    const getLayoutList = () => {
        if (layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND || layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN) {
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
                    <div className="p2-new text-black-700 mb-4 mt-6 px-4 !font-medium">Layout</div>
                    <div className="grid grid-cols-2 gap-2 border-b px-4 pb-6">
                        {getLayoutList().map((item: { style: FormSlideLayout; Icon: any }) => (
                            <div
                                key={item.style}
                                className={cn(
                                    'flex h-[50px] w-20 cursor-pointer items-center justify-center rounded-xl border-[1px] p-2 hover:bg-gray-200',

                                    layout && layout === item.style ? 'border-pink-500 ring-offset-1' : 'border-gray-200'
                                )}
                                onClick={() => handleSlideLayoutChange(activeSlideComponent?.id, item.style)}
                            >
                                {item.Icon && <item.Icon />}
                            </div>
                        ))}
                    </div>
                </>
            }
            {(activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page') && (
                <>
                    <div className="p2-new text-black-700 mb-4 mt-6 px-4 !font-medium">Settings</div>

                    <div className="flex w-full items-center justify-between border-b px-4 pb-4">
                        {activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page' ? (
                            <div className="flex w-full flex-col gap-4">
                                <div className="flex flex-row justify-between">
                                    <div className="text-black-700 text-xs">Description</div>
                                    <Switch
                                        checked={
                                            activeSlideComponent?.id === 'welcome-page' ? IsValidString(formState?.welcomePage?.description) : formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].message)
                                        }
                                        onCheckedChange={(checked) => {
                                            activeSlideComponent?.id === 'welcome-page' ? setFormDescription(checked ? '' : undefined) : setThankYouPageDescription(activeThankYouPageComponent?.index || 0, checked ? '' : undefined);
                                        }}
                                    />
                                </div>
                                {activeSlideComponent?.id === 'thank-you-page' ? (
                                    <div className="flex flex-col gap-3">
                                        <div className="flex flex-row justify-between">
                                            <div className="text-black-700 text-xs">Button</div>
                                            <Switch
                                                checked={formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText)}
                                                onCheckedChange={(checked) => {
                                                    setThankYouPageButtonText(activeThankYouPageComponent?.index || 0, checked ? '' : undefined);
                                                }}
                                            />
                                        </div>
                                        {formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText) && (
                                            <>
                                                <input
                                                    type="text"
                                                    placeholder="Try bettercollected"
                                                    value={formState.thankyouPage && formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText}
                                                    onChange={(e: any) => setThankYouPageButtonText(activeThankYouPageComponent?.index || 0, e.target.value)}
                                                    className="borer-[1px] border-black-300 focus:border-black-300 active:border-black-300 rounded-lg p-2 text-xs"
                                                />
                                                <div className="flex flex-row justify-between">
                                                    <div className="text-black-700 text-xs">Button Link</div>
                                                    <Switch
                                                        checked={formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink)}
                                                        onCheckedChange={(checked) => {
                                                            setThankYouPageButtonLink(activeThankYouPageComponent?.index || 0, checked ? '' : undefined);
                                                        }}
                                                    />
                                                </div>
                                                {formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink) && (
                                                    <input
                                                        type="text"
                                                        placeholder="Enter your link here"
                                                        value={formState.thankyouPage && formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink}
                                                        onChange={(e: any) => setThankYouPageButtonLink(activeThankYouPageComponent?.index || 0, e.target.value)}
                                                        className="borer-[1px] border-black-300 focus:border-black-300 active:border-black-300 rounded-lg p-2 text-xs"
                                                    />
                                                )}
                                            </>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-3">
                                        <div className="text-black-700 text-xs">Button</div>
                                        <input
                                            type="text"
                                            placeholder="Start"
                                            value={formState.welcomePage?.buttonText}
                                            onChange={(e: any) => setWelcomePageButtonText(e.target.value)}
                                            className="borer-[1px] border-black-300 focus:border-black-300 active:border-black-300 rounded-lg p-2 text-xs"
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
                </>
            )}
            {activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page' ? (
                <></>
            ) : (
                <>
                    <div className="p2-new text-black-700 mb-6 mt-6 px-4 !font-medium">Used Fields</div>
                    <div className="mb-4 flex flex-col gap-6 px-4">
                        {activeSlideComponent?.index !== undefined &&
                            formFields[activeSlideComponent.index]?.properties?.fields?.map((field) => {
                                return (
                                    <div key={field.id} className="text-black-700 flex items-center justify-between gap-2 text-xs">
                                        <div
                                            className="cursor-pointer truncate text-xs "
                                            onClick={() => {
                                                setActiveFieldComponent({
                                                    id: field.id,
                                                    index: field.index
                                                });
                                                const fieldElement = document.getElementById(`scroll-field-${field.id}`);
                                                fieldElement?.scrollIntoView({
                                                    behavior: 'smooth',
                                                    block: 'end',
                                                    inline: 'center'
                                                });
                                            }}
                                        >
                                            {extractTextfromJSON(field)}
                                        </div>
                                        <div
                                            className="h-5 w-5"
                                            onClick={() => {
                                                updateFieldRequired(field.index, activeSlideComponent.index, !field?.validations?.required);
                                            }}
                                        >
                                            <RequiredIcon className={cn('cursor-pointer', field?.validations?.required ? 'text-black-900' : 'text-[#DBDBDB]')} />
                                        </div>
                                    </div>
                                );
                            })}
                        {activeSlideComponent?.index !== undefined && (!formFields[activeSlideComponent.index]?.properties?.fields || !formFields[activeSlideComponent.index]?.properties?.fields?.length) && (
                            <div className="text-black-700z text-xs">No form fields in this page. Add elements to this page will be shown here</div>
                        )}
                    </div>
                </>
            )}
        </>
    );
}
