'use client';

import { Switch } from '@app/shadcn/components/ui/switch';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

export default function PagePropertiesTab() {
    const { formFields, updateShowQuestionNumbers, activeSlide } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const { formState, setFormState } = useFormState();
    return (
        <>
            <div className="p2-new mb-4 mt-6 px-4 !font-medium text-black-700">
                Layout
            </div>
            <div className="grid grid-cols-2 gap-2 border-b px-4 pb-6">
                {[1, 2, 3].map((item) => (
                    <div
                        key={item}
                        className="h-[50px] w-20 rounded-xl bg-gray-500"
                    ></div>
                ))}
            </div>
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
                                            className="borer-[1px] rounded-lg border-black-300 p-2 focus:border-black-300 active:border-black-300"
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
                                            className="borer-[1px] rounded-lg border-black-300 p-2 focus:border-black-300 active:border-black-300"
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
                                    className="borer-[1px] rounded-lg border-black-300 p-2 focus:border-black-300 active:border-black-300"
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
                                        <div className="truncate">
                                            {field?.title || 'Untitled Question'}
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
