'use client';

import Image from 'next/image';

import DeleteIcon from '@Components/icons/delete';
import SlideLayoutBackgroundImage from '@Components/icons/slide-layout-background-image';
import SlideLayoutLeftImage from '@Components/icons/slide-layout-left-image';
import SlideLayoutNoImage from '@Components/icons/slide-layout-no-image';
import { SlideLayoutNoImageLeftAlign } from '@Components/icons/slide-layout-no-image-left-align';
import SlideLayoutRightImage from '@Components/icons/slide-layout-right-image';
import { SwitchIcon } from '@Components/icons/switch-icon';
import { PlusIcon } from 'lucide-react';

import { formFieldsList } from '@app/constants/form-fields';
import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { useEndingActions } from '@app/lib/hooks/use-ending-actions';
import useGetPageAttributes from '@app/lib/hooks/use-get-page-attributes';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import { usePage } from '@app/store/jotai/entity-hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { defaultEndingIndex, ENDING_NAME_MAX_LENGTH } from '@app/utils/endings';
import { firstPartyImageProps } from '@app/utils/first-party-image';
import { SECTION_TITLE_MAX, isAnswerableField, leafletSection } from '@app/utils/leaflet-sections';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import { IsValidString } from '@app/utils/string-utils';
import { InspectorSection, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';
import PageJumpEditor from '@app/views/molecules/form-builder/page-jump-editor';

const NO_IMAGE_LAYOUTS = [FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN];

const inputClass = 'border-control focus:border-brand-500 rounded border p-2 text-xs';

/**
 * Page-level settings: the section title, the layout and its image, the
 * page's questions (a list that selects them; their own settings live in
 * the question panel) and the page's jumps. Welcome and ending pages get
 * their own description and button settings instead.
 */
export default function PagePropertiesTab({}: {}) {
    const { getFormFields, updateSlideLayout, updateSlideImage, setFormFields, updateSlideSectionTitle } = useBuilderActions();
    const { activeSlideComponent } = useActiveSlideComponent();
    // The selected page only (its questions are listed below).
    const activeSlide = usePage(activeSlideComponent?.id);
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

    const isWelcome = activeSlideComponent?.id === 'welcome-page';
    const isEnding = activeSlideComponent?.id === 'thank-you-page';
    const endingIndex = activeThankYouPageComponent?.index || 0;
    const ending = formState.thankyouPage?.[endingIndex];
    const endingActions = useEndingActions();
    const { renameEnding, makeDefault } = endingActions;

    const slide = activeSlideComponent && (activeSlideComponent.index >= 0 ? activeSlide : activeSlideComponent.index === -10 ? formState.welcomePage : formState.thankyouPage?.[endingIndex]);

    function updatePagesLayout() {
        if (
            (activeSlide?.properties?.layout && NO_IMAGE_LAYOUTS.includes(activeSlide?.properties?.layout)) ||
            (activeSlideComponent &&
                ((formState.welcomePage?.layout && NO_IMAGE_LAYOUTS.includes(formState.welcomePage?.layout)) || NO_IMAGE_LAYOUTS.includes(formState.thankyouPage?.[endingIndex]?.layout ?? FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN)))
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

    const pickImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage: getPageImageUpdateFunction
        });
    };

    function getPageIndex() {
        if (isWelcome) return -10;
        else if (isEnding) return -20;
        else return activeSlide?.index;
    }
    const { layout } = useGetPageAttributes(getPageIndex() ?? -10);

    const layoutOptions: Array<{ style: FormSlideLayout; Icon: any; label: string }> =
        layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND || layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
            ? [
                  { style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN, Icon: SlideLayoutNoImageLeftAlign, label: 'Left aligned' },
                  { style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, Icon: SlideLayoutNoImage, label: 'Centered' }
              ]
            : [
                  { style: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, Icon: SlideLayoutRightImage, label: 'Image right' },
                  { style: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT, Icon: SlideLayoutLeftImage, label: 'Image left' },
                  { style: FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND, Icon: SlideLayoutBackgroundImage, label: 'Image fill' }
              ];

    const handleSlideLayoutChange = (newLayout: FormSlideLayout) => {
        if (isWelcome) updateWelcomePageLayout(newLayout);
        else if (isEnding) updateThankYouPageLayout(newLayout);
        else updateSlideLayout(newLayout);
    };

    const handleRemoveImage = () => {
        const noImage = { imageUrl: '', layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND };
        if (isWelcome && formState.welcomePage) {
            setFormState({ ...formState, welcomePage: { ...formState.welcomePage, ...noImage } });
        } else if (isEnding && formState.thankyouPage) {
            setFormState({ ...formState, thankyouPage: formState.thankyouPage.map((page, index) => (index === endingIndex ? { ...page, ...noImage } : page)) });
        } else {
            const pageIndex = activeSlideComponent?.index || 0;
            const formFields = getFormFields();
            if (!formFields[pageIndex]) return;
            setFormFields(formFields.map((page, index) => (index === pageIndex ? { ...page, imageUrl: '', properties: { ...page.properties, layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND } } : page)));
        }
    };

    const questionPage = !isWelcome && !isEnding && (activeSlideComponent?.index ?? -1) >= 0 ? activeSlide : undefined;
    const sectionFallback = questionPage ? leafletSection(questionPage.properties?.fields ?? [], `Section ${activeSlideComponent!.index + 1}`).shortTitle : '';
    const pageQuestions = questionPage?.properties?.fields ?? [];

    const selectQuestion = (field: { id: string; index: number }) => {
        setActiveFieldComponent({ id: field.id, index: field.index });
        document.getElementById(`scroll-field-${field.id}`)?.scrollIntoView?.({ behavior: 'smooth', inline: 'center' });
    };

    return (
        <>
            {questionPage && (
                <InspectorSection title="Section title">
                    <div className="-mt-2 flex flex-col gap-2">
                        <input
                            id="page-section-title"
                            type="text"
                            aria-label="Section title"
                            maxLength={SECTION_TITLE_MAX}
                            value={questionPage.properties?.sectionTitle ?? ''}
                            placeholder={sectionFallback}
                            aria-describedby="page-section-title-hint"
                            onChange={(event) => updateSlideSectionTitle(activeSlideComponent!.index, event.target.value)}
                            className={inputClass}
                        />
                        <p id="page-section-title-hint" className="text-xs leading-[1.5] text-black-600">
                            Shown on the section bar and in the contents list when the form uses the Leaflet style; you can also edit it on the bar itself. Leave empty to use the page&apos;s opening heading, else its first question.
                        </p>
                    </div>
                </InspectorSection>
            )}

            <InspectorSection title="Layout">
                <div className="grid grid-cols-2 gap-2" role="group" aria-label="Page layout">
                    {layoutOptions.map((item) => {
                        const selected = layout === item.style;
                        return (
                            <button
                                key={item.style}
                                type="button"
                                aria-pressed={selected}
                                data-umami-event={`${item.style} Layout`}
                                onClick={() => handleSlideLayoutChange(item.style)}
                                className="group flex flex-col items-center gap-1 rounded-lg"
                            >
                                <span
                                    aria-hidden="true"
                                    className={cn(
                                        'flex h-[50px] w-20 items-center justify-center rounded-lg border p-2 transition-colors group-hover:border-brand-500 group-hover:bg-[#F4F7FD]',
                                        selected ? 'border-brand-500 bg-[#F4F7FD] ring-1 ring-brand-500' : 'border-black-300 bg-white'
                                    )}
                                >
                                    {item.Icon && <item.Icon />}
                                </span>
                                <span className={cn('text-[10px]', selected ? 'font-medium text-black-800' : 'text-black-600')}>{item.label}</span>
                            </button>
                        );
                    })}
                </div>
                <div className={cn('flex justify-between gap-2', slide?.imageUrl ? 'flex-col items-start' : 'flex-row items-center')}>
                    <span className="text-xs text-black-700">Layout image</span>
                    {slide?.imageUrl ? (
                        <div className="group relative w-full">
                            <div className="absolute top-2 left-2 z-10 flex gap-2 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                                <button type="button" aria-label="Remove layout image" className="rounded-md bg-white p-2 shadow-large" onClick={handleRemoveImage}>
                                    <DeleteIcon width={16} height={16} aria-hidden="true" />
                                </button>
                                <button type="button" aria-label="Change layout image" className="rounded-md bg-white p-2 shadow-large" onClick={pickImage}>
                                    <SwitchIcon width={16} height={16} aria-hidden="true" />
                                </button>
                            </div>
                            <Image style={{ objectFit: 'contain', width: 'fit-content', maxHeight: '168px' }} sizes="100vw" {...firstPartyImageProps(slide.imageUrl)} alt="" height={0} width={0} priority />
                        </div>
                    ) : (
                        <button type="button" aria-label="Add layout image" className="rounded border border-black-300 p-1 hover:bg-black-200" onClick={pickImage}>
                            <PlusIcon className="h-4 w-4" aria-hidden="true" />
                        </button>
                    )}
                </div>
            </InspectorSection>

            {(isWelcome || isEnding) && (
                <InspectorSection title="Settings">
                    <SettingSwitch
                        label="Description"
                        checked={!!(isWelcome ? IsValidString(formState?.welcomePage?.description) : ending && IsValidString(ending.message))}
                        onCheckedChange={(checked) => (isWelcome ? setFormDescription(checked ? '' : undefined) : setThankYouPageDescription(endingIndex, checked ? '' : undefined))}
                    />
                    {isEnding ? (
                        <>
                            <div className="flex flex-col gap-1">
                                <label htmlFor="ending-name" className="text-xs text-black-700">
                                    Name
                                </label>
                                <input
                                    id="ending-name"
                                    type="text"
                                    maxLength={ENDING_NAME_MAX_LENGTH}
                                    placeholder="e.g. Eligible"
                                    aria-describedby="ending-name-hint"
                                    value={ending?.name ?? ''}
                                    onChange={(e) => renameEnding(endingIndex, e.target.value)}
                                    className={inputClass}
                                />
                                <span id="ending-name-hint" className="text-[11px] text-black-600">
                                    For you and page jumps; respondents never see it.
                                </span>
                            </div>
                            {endingActions.endings.length > 1 && (
                                <SettingSwitch
                                    label="Default ending"
                                    checked={defaultEndingIndex(endingActions.endings) === endingIndex}
                                    hint="Shown after a plain submit, and when no jump chooses another ending. To change it, turn it on for another ending."
                                    disabled={defaultEndingIndex(endingActions.endings) === endingIndex}
                                    onCheckedChange={(checked) => checked && makeDefault(endingIndex)}
                                />
                            )}
                            <SettingSwitch label="Button" checked={!!(ending && IsValidString(ending.buttonText))} onCheckedChange={(checked) => setThankYouPageButtonText(endingIndex, checked ? 'Try bettercollected' : undefined)} />
                            {ending && IsValidString(ending.buttonText) && (
                                <>
                                    <input type="text" aria-label="Button text" placeholder="Try bettercollected" value={ending.buttonText ?? ''} onChange={(e) => setThankYouPageButtonText(endingIndex, e.target.value)} className={inputClass} />
                                    <SettingSwitch label="Button link" checked={IsValidString(ending.buttonLink)} onCheckedChange={(checked) => setThankYouPageButtonLink(endingIndex, checked ? 'https://bettercollected.com' : undefined)} />
                                    {IsValidString(ending.buttonLink) && (
                                        <input type="text" aria-label="Button link" placeholder="Enter your link here" value={ending.buttonLink ?? ''} onChange={(e) => setThankYouPageButtonLink(endingIndex, e.target.value)} className={inputClass} />
                                    )}
                                </>
                            )}
                        </>
                    ) : (
                        <div className="flex flex-col gap-1">
                            <label htmlFor="welcome-button-text" className="text-xs text-black-700">
                                Button
                            </label>
                            <input id="welcome-button-text" type="text" placeholder="Start" value={formState.welcomePage?.buttonText || ''} onChange={(e) => setWelcomePageButtonText(e.target.value)} className={inputClass} />
                        </div>
                    )}
                </InspectorSection>
            )}

            {questionPage && pageQuestions.length > 0 && (
                <InspectorSection title="Questions">
                    {/* A way to the questions, not a second place to edit them:
                        width, Required and the rest live in the question panel. */}
                    <ol className="-mx-2 -mt-2 flex flex-col" aria-label="Questions on this page">
                        {pageQuestions.map((field) => {
                            const title = extractTextfromJSON(field).trim();
                            const typeName = formFieldsList.find((f) => f.type === field.type)?.name ?? '';
                            return (
                                <li key={field.id}>
                                    <button type="button" onClick={() => selectQuestion(field)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-black-200">
                                        <span className="min-w-0 flex-1 truncate text-black-800">{title || typeName || 'Untitled'}</span>
                                        {isAnswerableField(field) && field.validations?.required && <span className="shrink-0 text-[10px] text-black-600">Required</span>}
                                    </button>
                                </li>
                            );
                        })}
                    </ol>
                </InspectorSection>
            )}

            {questionPage && <PageJumpEditor />}
        </>
    );
}
