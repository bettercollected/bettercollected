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

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
import { useAuthAtom } from '@app/store/jotai/auth';
import { IsValidString } from '@app/utils/stringUtils';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import { PlusIcon } from '@app/views/atoms/Icons/Plus';
import { SwitchIcon } from '@app/views/atoms/Icons/SwitchIcon';
import Image from 'next/image';
import SlideLayoutBackgroundImage from '../../atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '../../atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '../../atoms/Icons/SlideLayoutNoImage';
import SlideLayoutRightImage from '../../atoms/Icons/SlideLayoutRightImage';

export default function PagePropertiesTab({}: {}) {
    const { formFields, activeSlide, updateSlideLayout, updateSlideImage, setFormFields } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    const { authState } = useAuthAtom();
    const {
        formState,
        setFormState,
        setWelcomePageButtonText,
        setThankYouPageDescription,
        setThankYouPageButtonText,
        setThankYouPageButtonLink,
        updateThankYouPageLayout,
        updateWelcomePageLayout,
        setFormDescription,
        updateWelcomePageImage,
        updateThankYouPageImage
    } = useFormState();

    const { openDialogModal } = useDialogModal();

    const NO_IMAGE_LAYOUTS = [FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN];

    const slide = activeSlideComponent && (activeSlideComponent.index >= 0 ? formFields[activeSlideComponent.index] : activeSlideComponent.index === -10 ? formState.welcomePage : formState.thankyouPage![activeThankYouPageComponent?.index || 0]);

    function updatePagesLayout() {
        if (
            (activeSlide?.properties?.layout && NO_IMAGE_LAYOUTS.includes(activeSlide?.properties?.layout)) ||
            (activeSlideComponent &&
                ((formState.welcomePage?.layout && NO_IMAGE_LAYOUTS.includes(formState.welcomePage?.layout)) ||
                    NO_IMAGE_LAYOUTS.includes(formState.thankyouPage![activeThankYouPageComponent?.index || 0]?.layout ?? FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)))
        ) {
            if (activeSlideComponent?.index === -10) {
                updateWelcomePageLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            } else if (activeSlideComponent?.index === -20) {
                updateThankYouPageLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            } else {
                updateSlideLayout(FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT);
            }
        }
    }

    function getPageImageUpdateFunction(image: string) {
        if (image) {
            updatePagesLayout();
        }
        if (activeSlideComponent?.index === -10) {
            updateWelcomePageImage(image);
        } else if (activeSlideComponent?.index === -20) {
            updateThankYouPageImage(image);
        } else {
            updateSlideImage(image);
        }
    }

    const handleClickMedia = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage: getPageImageUpdateFunction
        });
    };

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

    const handleRemoveImage = (slideId?: string) => {
        if (slideId) {
            if (slideId === 'welcome-page' && formState.welcomePage) {
                formState.welcomePage.imageUrl = '';
                formState.welcomePage.layout = FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND;
                setFormState({ ...formState });
            } else if (slideId === 'thank-you-page' && formState.thankyouPage) {
                formState.thankyouPage[activeThankYouPageComponent?.index || 0].imageUrl = '';
                formState.thankyouPage[activeThankYouPageComponent?.index || 0].layout = FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND;
                setFormState({ ...formState });
            } else {
                formFields[activeSlideComponent?.index || 0].imageUrl = '';
                formFields[activeSlideComponent?.index || 0] && (formFields[activeSlideComponent?.index || 0]!.properties!.layout = FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
                setFormFields([...formFields]);
            }
        }
    };

    const handleChangeImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage: getPageImageUpdateFunction
        });
    };

    return (
        <>
            {
                <>
                    <div className="p2-new text-black-700 mb-4 mt-6 px-4 !font-medium">Layout</div>
                    <div className="grid grid-cols-2 gap-2 border-b px-4 pb-6">
                        {getLayoutList().map((item: { style: FormSlideLayout; Icon: any }) => (
                            <button key={item.style} data-umami-event={`${item.style} Layout`} data-umami-event-email={authState.email}>
                                <div
                                    className={cn(
                                        'flex h-[50px] w-20 cursor-pointer items-center justify-center rounded-xl border-[1px] p-2 hover:bg-gray-200',

                                        layout && layout === item.style ? 'border-pink-500 ring-offset-1' : 'border-gray-200'
                                    )}
                                    onClick={() => handleSlideLayoutChange(activeSlideComponent?.id, item.style)}
                                >
                                    {item.Icon && <item.Icon />}
                                </div>
                            </button>
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
                                                    value={(formState.thankyouPage && formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText) ?? ''}
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
                            <></>
                        )}
                    </div>
                </>
            )}
            <div className={cn('border-black-200 flex justify-between border-b px-4 py-6 hover:bg-inherit', slide?.imageUrl ? 'flex-col items-start gap-2' : 'flex-row items-center ')}>
                <span className="p3-new text-black-700">Layout Image</span>
                {slide?.imageUrl ? (
                    <div className={`group relative my-4 max-h-[168px] w-full`}>
                        <div className={cn('absolute hidden h-full w-full items-start justify-start gap-2 p-2 group-hover:flex')}>
                            <div className="shadow-bubble cursor-pointer rounded-md bg-white p-2" onClick={() => handleRemoveImage(activeSlideComponent?.id)}>
                                <DeleteIcon width={16} height={16} />
                            </div>
                            <div className=" shadow-bubble cursor-pointer rounded-md bg-white p-2" onClick={handleChangeImage}>
                                <SwitchIcon width={16} height={16} />
                            </div>
                        </div>
                        <Image style={{ objectFit: 'contain', width: 'fit-content', maxHeight: '168px' }} sizes="100vw" src={slide.imageUrl} alt={' image'} height={0} width={0} priority />
                    </div>
                ) : (
                    <div className="border-black-300 hover:bg-black-300 cursor-pointer rounded border-[1px] p-1" onClick={handleClickMedia}>
                        <PlusIcon className="h-4 w-4" />
                    </div>
                )}
            </div>
            {activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page' ? (
                <></>
            ) : activeSlideComponent?.index !== undefined && (!formFields[activeSlideComponent.index]?.properties?.fields || !formFields[activeSlideComponent.index]?.properties?.fields?.length) ? (
                // <div className="text-black-700z text-xs">No form fields in this page. Add elements to this page will be shown here</div>
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
                                                    inline: 'center'
                                                });
                                            }}
                                        >
                                            {extractTextfromJSON(field)}
                                        </div>
                                        {field.type !== FieldTypes.TEXT && (
                                            <div
                                                className="h-5 w-5"
                                                onClick={() => {
                                                    updateFieldRequired(field.index, activeSlideComponent.index, !field?.validations?.required);
                                                }}
                                            >
                                                <RequiredIcon className={cn('cursor-pointer', field?.validations?.required ? 'text-black-900' : 'text-[#DBDBDB]')} />
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                    </div>
                </>
            )}
        </>
    );
}
