'use client';

import Image from 'next/image';

import DeleteIcon from '@Components/icons/delete';
import RequiredIcon from '@Components/icons/required';
import SlideLayoutBackgroundImage from '@Components/icons/slide-layout-background-image';
import SlideLayoutLeftImage from '@Components/icons/slide-layout-left-image';
import SlideLayoutNoImage from '@Components/icons/slide-layout-no-image';
import { SlideLayoutNoImageLeftAlign } from '@Components/icons/slide-layout-no-image-left-align';
import SlideLayoutRightImage from '@Components/icons/slide-layout-right-image';
import { SwitchIcon } from '@Components/icons/switch-icon';
import { PlusIcon } from 'lucide-react';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import useGetPageAttributes from '@app/lib/hooks/use-get-page-attributes';
import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { firstPartyImageProps } from '@app/utils/first-party-image';
import { SECTION_TITLE_MAX, leafletSection } from '@app/utils/leaflet-sections';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { IsValidString } from '@app/utils/string-utils';
import PageJumpEditor from '@app/views/molecules/form-builder/page-jump-editor';

export default function PagePropertiesTab({}: {}) {
    const { formFields, activeSlide, updateSlideLayout, updateSlideImage, setFormFields, updateSlideSectionTitle } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
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

    const { updateFieldRequired, updateFieldColSpan } = useFormFieldsAtom();

    const getLayoutList = () => {
        if (layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND || layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN) {
            return [
                {
                    style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN,
                    Icon: SlideLayoutNoImageLeftAlign,
                    label: 'Left aligned'
                },
                {
                    style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                    Icon: SlideLayoutNoImage,
                    label: 'Centered'
                }
            ];
        } else
            return [
                {
                    style: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                    Icon: SlideLayoutRightImage,
                    label: 'Image right'
                },
                {
                    style: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT,
                    Icon: SlideLayoutLeftImage,
                    label: 'Image left'
                },
                {
                    style: FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND,
                    Icon: SlideLayoutBackgroundImage,
                    label: 'Image fill'
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

    const questionPage = activeSlideComponent?.id !== 'welcome-page' && activeSlideComponent?.id !== 'thank-you-page' && (activeSlideComponent?.index ?? -1) >= 0 ? formFields[activeSlideComponent!.index] : undefined;
    const sectionFallback = questionPage ? leafletSection(questionPage.properties?.fields ?? [], `Section ${activeSlideComponent!.index + 1}`).shortTitle : '';

    return (
        <>
            {questionPage && (
                <div className="flex flex-col gap-2 border-b px-4 pt-4 pb-4">
                    <label htmlFor="page-section-title" className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                        Section title
                    </label>
                    <input
                        id="page-section-title"
                        type="text"
                        maxLength={SECTION_TITLE_MAX}
                        value={questionPage.properties?.sectionTitle ?? ''}
                        placeholder={sectionFallback}
                        aria-describedby="page-section-title-hint"
                        onChange={(event) => updateSlideSectionTitle(activeSlideComponent!.index, event.target.value)}
                        className="rounded border border-control p-2 text-xs focus:border-brand-500"
                    />
                    <p id="page-section-title-hint" className="text-xs leading-[1.5] text-black-600">
                        Shown on the section bar and in the contents list when the form uses the Leaflet style. Leave empty to use the page&apos;s opening heading, else its first question.
                    </p>
                </div>
            )}
            {
                <>
                    <div className="px-4 pt-4 pb-3 text-xs font-semibold tracking-wide text-black-600 uppercase">Layout</div>
                    <div className="grid grid-cols-2 gap-2 border-b px-4 pb-4">
                        {getLayoutList().map((item: { style: FormSlideLayout; Icon: any; label: string }) => (
                            <button key={item.style} data-umami-event={`${item.style} Layout`} className="flex flex-col items-center gap-1">
                                <div
                                    className={cn(
                                        'flex h-[50px] w-20 cursor-pointer items-center justify-center rounded-lg border p-2 transition-colors hover:border-brand-500 hover:bg-[#F4F7FD]',
                                        layout && layout === item.style ? 'border-brand-500 bg-[#F4F7FD] ring-1 ring-brand-500' : 'border-black-300 bg-white'
                                    )}
                                    onClick={() => handleSlideLayoutChange(activeSlideComponent?.id, item.style)}
                                >
                                    {item.Icon && <item.Icon />}
                                </div>
                                <span className={cn('text-[10px]', layout && layout === item.style ? 'font-medium text-black-800' : 'text-black-600')}>{item.label}</span>
                            </button>
                        ))}
                    </div>
                </>
            }
            {(activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page') && (
                <>
                    <div className="px-4 pt-4 pb-3 text-xs font-semibold tracking-wide text-black-600 uppercase">Settings</div>

                    <div className="flex w-full items-center justify-between border-b px-4 pb-4">
                        {activeSlideComponent?.id === 'welcome-page' || activeSlideComponent?.id === 'thank-you-page' ? (
                            <div className="flex w-full flex-col gap-4">
                                <div className="flex flex-row justify-between">
                                    <div className="text-xs text-black-700">Description</div>
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
                                            <div className="text-xs text-black-700">Button</div>
                                            <Switch
                                                checked={formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonText)}
                                                onCheckedChange={(checked) => {
                                                    setThankYouPageButtonText(activeThankYouPageComponent?.index || 0, checked ? 'Try bettercollected' : undefined);
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
                                                    className="rounded border border-control p-2 text-xs focus:border-brand-500"
                                                />
                                                <div className="flex flex-row justify-between">
                                                    <div className="text-xs text-black-700">Button Link</div>
                                                    <Switch
                                                        checked={formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink)}
                                                        onCheckedChange={(checked) => {
                                                            setThankYouPageButtonLink(activeThankYouPageComponent?.index || 0, checked ? 'https://bettercollected.com' : undefined);
                                                        }}
                                                    />
                                                </div>
                                                {formState.thankyouPage && IsValidString(formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink) && (
                                                    <input
                                                        type="text"
                                                        placeholder="Enter your link here"
                                                        value={formState.thankyouPage && formState.thankyouPage[activeThankYouPageComponent?.index || 0].buttonLink}
                                                        onChange={(e: any) => setThankYouPageButtonLink(activeThankYouPageComponent?.index || 0, e.target.value)}
                                                        className="rounded border border-control p-2 text-xs focus:border-brand-500"
                                                    />
                                                )}
                                            </>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-3">
                                        <div className="text-xs text-black-700">Button</div>
                                        <input
                                            type="text"
                                            placeholder="Start"
                                            value={formState.welcomePage?.buttonText || ''}
                                            onChange={(e: any) => setWelcomePageButtonText(e.target.value)}
                                            className="rounded border border-control p-2 text-xs focus:border-brand-500"
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
            <div className={cn('flex justify-between border-b border-black-300 px-4 py-4 hover:bg-inherit', slide?.imageUrl ? 'flex-col items-start gap-2' : 'flex-row items-center')}>
                <span className="text-xs font-semibold tracking-wide text-black-600 uppercase">Layout Image</span>
                {slide?.imageUrl ? (
                    <div className={`group relative my-4 max-h-[168px] w-full`}>
                        <div className={cn('absolute hidden h-full w-full items-start justify-start gap-2 p-2 group-hover:flex')}>
                            <div className="cursor-pointer rounded-md bg-white p-2 shadow-large" onClick={() => handleRemoveImage(activeSlideComponent?.id)}>
                                <DeleteIcon width={16} height={16} />
                            </div>
                            <div className="cursor-pointer rounded-md bg-white p-2 shadow-large" onClick={handleChangeImage}>
                                <SwitchIcon width={16} height={16} />
                            </div>
                        </div>
                        <Image style={{ objectFit: 'contain', width: 'fit-content', maxHeight: '168px' }} sizes="100vw" {...firstPartyImageProps(slide.imageUrl)} alt={' image'} height={0} width={0} priority />
                    </div>
                ) : (
                    <div className="cursor-pointer rounded border border-black-300 p-1 hover:bg-black-300" onClick={handleClickMedia}>
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
                    <div className="px-4 pt-4 pb-2 text-xs font-semibold tracking-wide text-black-600 uppercase">Used Fields</div>
                    <div className="mb-4 flex flex-col gap-3 px-4">
                        {activeSlideComponent?.index !== undefined &&
                            formFields[activeSlideComponent.index]?.properties?.fields?.map((field) => {
                                return (
                                    <div key={field.id} className="flex items-center justify-between gap-2 text-xs text-black-700">
                                        <div
                                            className="cursor-pointer truncate text-xs"
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
                                        <div className="flex shrink-0 items-center gap-1.5">
                                            {/* 12-grid width: full row, halves, thirds… adjacent
                                                fields whose spans fit share a row on desktop. */}
                                            <select
                                                aria-label="Field width"
                                                title="Field width (12-column grid)"
                                                value={String(Math.min(12, Math.max(1, field?.properties?.colSpan ?? 12)))}
                                                onChange={(e) => updateFieldColSpan(field.index, activeSlideComponent.index, Number(e.target.value))}
                                                className="h-5 cursor-pointer rounded border border-black-300 bg-white px-0.5 text-[10px] text-black-700 outline-hidden hover:border-black-400"
                                            >
                                                <option value="12">Full</option>
                                                <option value="8">2/3</option>
                                                <option value="6">1/2</option>
                                                <option value="4">1/3</option>
                                                <option value="3">1/4</option>
                                            </select>
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
                                    </div>
                                );
                            })}
                    </div>
                </>
            )}
            {activeSlideComponent?.id !== 'welcome-page' && activeSlideComponent?.id !== 'thank-you-page' && (activeSlideComponent?.index ?? -1) >= 0 && (
                <>
                    <div className="border-t">
                        <PageJumpEditor />
                    </div>
                </>
            )}
        </>
    );
}
