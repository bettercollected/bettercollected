'use client';

import parse from 'html-react-parser';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { getHtmlFromJson } from '@app/utils/richTextEditorExtenstion/getHtmlFromJson';

import SlideLayoutBackgroundImage from '../../atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '../../atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '../../atoms/Icons/SlideLayoutNoImage';
import SlideLayoutRightImage from '../../atoms/Icons/SlideLayoutRightImage';
import { getPlaceholderValueForTitle } from '../../molecules/RichTextEditor';

export default function PagePropertiesTab({}: {}) {
    const {
        formFields,
        updateShowQuestionNumbers,
        activeSlide,
        updateSlideLayout,
        updateSlideImage
    } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();

    const { openDialogModal } = useDialogModal();

    // Function to handle layout update for a specific slide
    const handleSlideLayoutChange = (slideId?: string, newLayout?: FormSlideLayout) => {
        if (slideId && newLayout) updateSlideLayout(newLayout);
    };

    const { formState, setFormState } = useFormState();
    return (
        <>
            {activeSlide && (
                <>
                    <div className="p2-new mb-4 mt-6 px-4 !font-medium text-black-700">
                        Layout
                    </div>
                    <div className="grid grid-cols-2 gap-2 border-b px-4 pb-6">
                        {[
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
                            },
                            {
                                style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                                Icon: SlideLayoutNoImage
                            }
                        ].map((item: { style: FormSlideLayout; Icon: any }) => (
                            <div
                                key={item.style}
                                className={cn(
                                    'flex h-[50px] w-20 cursor-pointer items-center justify-center rounded-xl border-[1px] p-2 hover:bg-gray-200',
                                    activeSlide &&
                                        activeSlide.properties?.layout === item.style
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
                        ))}
                    </div>
                </>
            )}

            {activeSlide?.properties?.layout &&
                activeSlide?.properties?.layout !==
                    FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND && (
                    <>
                        <div className="p2-new mb-4 mt-6 px-4 !font-medium text-black-700">
                            Background Image
                        </div>
                        <div className="flex w-full items-center justify-between border-b px-4 pb-4">
                            <div className="flex w-full flex-col gap-4">
                                {activeSlide?.imageUrl ? (
                                    <Button
                                        variant="danger"
                                        onClick={() => updateSlideImage('')}
                                        className="!h-auto py-2"
                                    >
                                        Remove Image
                                    </Button>
                                ) : (
                                    <Button
                                        variant="secondary"
                                        onClick={() =>
                                            openDialogModal('UNSPLASH_IMAGE_PICKER', {
                                                activeSlide,
                                                updateSlideImage
                                            })
                                        }
                                        className="!h-auto py-2"
                                    >
                                        Select Layout Image
                                    </Button>
                                )}
                            </div>
                        </div>
                    </>
                )}
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
                                        ? formState.description !== undefined
                                        : formState.thankYouMessage !== undefined
                                }
                                onCheckedChange={(checked) => {
                                    activeSlideComponent?.id === 'welcome-page'
                                        ? setFormState({
                                              ...formState,
                                              description: checked ? '' : undefined
                                          })
                                        : setFormState({
                                              ...formState,
                                              thankYouMessage: checked ? '' : undefined
                                          });
                                }}
                            />
                        </div>
                        {activeSlideComponent?.id === 'thank-you-page' ? (
                            <div className="flex flex-col gap-3">
                                <div className="flex flex-row justify-between">
                                    <div className="text-xs text-black-700">Button</div>
                                    <Switch
                                        checked={
                                            formState.thankYouButtonText !== undefined
                                        }
                                        onCheckedChange={(checked) => {
                                            setFormState({
                                                ...formState,
                                                thankYouButtonText: checked
                                                    ? ''
                                                    : undefined
                                            });
                                        }}
                                    />
                                </div>
                                {formState.thankYouButtonText !== undefined && (
                                    <>
                                        <input
                                            type="text"
                                            placeholder="buttonText"
                                            value={formState.thankYouButtonText}
                                            onChange={(e: any) =>
                                                setFormState({
                                                    ...formState,
                                                    thankYouButtonText: e.target.value
                                                })
                                            }
                                            className="borer-[1px] rounded-lg border-black-300 p-2 text-xs focus:border-black-300 active:border-black-300"
                                        />
                                        <div className="flex flex-row justify-between">
                                            <div className="text-xs text-black-700">
                                                Button Link
                                            </div>
                                            <Switch
                                                checked={
                                                    formState.buttonLink !== undefined
                                                }
                                                onCheckedChange={(checked) => {
                                                    setFormState({
                                                        ...formState,
                                                        buttonLink: checked
                                                            ? ''
                                                            : undefined
                                                    });
                                                }}
                                            />
                                        </div>
                                        <input
                                            type="text"
                                            placeholder="buttonLink"
                                            value={formState.buttonLink}
                                            onChange={(e: any) =>
                                                setFormState({
                                                    ...formState,
                                                    buttonLink: e.target.value
                                                })
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
                                    placeholder="buttonText"
                                    value={formState.buttonText}
                                    onChange={(e: any) =>
                                        setFormState({
                                            ...formState,
                                            buttonText: e.target.value
                                        })
                                    }
                                    className="borer-[1px] rounded-lg border-black-300 p-2 text-xs focus:border-black-300 active:border-black-300"
                                />
                            </div>
                        )}
                    </div>
                ) : (
                    <>
                        <div className="text-xs text-black-700">Question Numbers</div>
                        <Switch
                            checked={
                                activeSlide?.properties?.showQuestionNumbers || false
                            }
                            onCheckedChange={(checked) => {
                                updateShowQuestionNumbers(activeSlide!.index, checked);
                            }}
                        />
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
                                        <div className="truncate text-xs">
                                            {parse(
                                                getHtmlFromJson(field?.title) ??
                                                    getPlaceholderValueForTitle(
                                                        field.type || FieldTypes.TEXT
                                                    )
                                            )}
                                        </div>
                                        <svg
                                            width="20"
                                            height="20"
                                            viewBox="0 0 20 20"
                                            fill="none"
                                            className={
                                                field?.validations?.required
                                                    ? 'text-pink-500'
                                                    : 'text-[#DBDBDB]'
                                            }
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
