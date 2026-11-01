'use client';

import i18n from 'i18next';
import { useEffect } from 'react';

import { useAtom } from 'jotai';

import { useTranslation } from 'react-i18next';
import { formFieldsList } from '@app/constants/form-fields';
import { fieldTypeChip } from '@app/lib/field-type-name';
import { InspectorLevel, inspectorLevel } from '@app/lib/hooks/use-inspector-escape';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { activeContainerAtom, useActiveFieldComponent, useActiveSlideComponent, useActiveThankYouPageComponent } from '@app/store/jotai/active-builder-component';
import { useField } from '@app/store/jotai/entity-hooks';
import { useFormState } from '@app/store/jotai/form';
import { PropertiesTab, usePropertiesTab } from '@app/store/jotai/properties-tab';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import InspectorBreadcrumb, { InspectorCrumb } from '@app/views/molecules/form-builder/inspector-breadcrumb';
import LayoutContainerSettings from '@app/views/molecules/form-builder/layout-container-settings';
import FieldSettings from '@app/views/organism/field-settings';
import AIChatTab from '@app/views/organism/form-builder/ai-chat-tab';
import FormSettingsTab from '@app/views/organism/form-builder/form-settings-tab';
import PageDesignTab from '@app/views/organism/form-builder/page-design-tab';
import PagePropertiesTab from '@app/views/organism/form-builder/page-properties-tab';

/** What the Page crumb says for the selected page; an ending by its name, else its title. */
export function pageCrumbLabel(slide: { id?: string; index?: number } | null | undefined, ending?: { name?: string; title?: string } | null): string {
    if (!slide) return i18n.t('builder:PAGE_PROPS.CRUMB_PAGE');
    if (slide.id === 'welcome-page') return i18n.t('builder:PAGE_PROPS.CRUMB_WELCOME');
    if (slide.id === 'thank-you-page') return ending?.name?.trim() || ending?.title?.trim() || i18n.t('builder:OUTLINE.ENDING');
    return i18n.t('builder:OUTLINE.PAGE_N', { n: (slide.index ?? 0) + 1 });
}

const TABS: Array<{ value: PropertiesTab; label: string }> = [
    { value: 'page', label: 'PAGE_PROPS.TAB_PAGE' },
    { value: 'form', label: 'PAGE_PROPS.TAB_FORM' },
    { value: 'design', label: 'PAGE_PROPS.TAB_DESIGN' },
    { value: 'ai', label: 'PAGE_PROPS.TAB_AI' }
];

/**
 * The builder's inspector (right sidebar). A breadcrumb always says where
 * it is (Form › Page 2 › Question) and goes back up; Escape does the same
 * (lib/hooks/use-inspector-escape.ts). With a question selected it shows
 * that question's settings; otherwise the page and form settings, in tabs.
 */
export default function PropertiesDrawer({}: {}) {
    const { t } = useTranslation('builder');
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { propertiesTab, setPropertiesTab } = usePropertiesTab();
    // The selected question only: typing in another one leaves the inspector alone.
    const activeField = useField(activeFieldComponent?.id);
    const standardForm = useAppSelector(selectForm);
    const { formState } = useFormState();
    const { activeThankYouPageComponent } = useActiveThankYouPageComponent();
    // A panel, field set or tabs strip selected on the canvas (no question is then)
    const [activeContainer, setActiveContainer] = useAtom(activeContainerAtom);
    // ... which belongs to the page it is on
    useEffect(() => {
        if (activeContainer && activeSlideComponent?.id !== activeContainer.pageId) setActiveContainer(null);
    }, [activeContainer, activeSlideComponent?.id]);

    // Start-with-AI handoff: a pending prompt (stashed by the dashboard
    // dialog) opens the drawer on the AI tab; the tab itself consumes and
    // sends it.
    useEffect(() => {
        if (standardForm?.formId && typeof window !== 'undefined' && sessionStorage.getItem(`bc:ai-prompt:${standardForm.formId}`)) {
            setPropertiesTab('ai');
        }
    }, [standardForm?.formId]);

    const level = inspectorLevel(!!activeFieldComponent?.id, propertiesTab);
    const questionLabel = activeField ? extractTextfromJSON(activeField).trim() || fieldTypeChip(t, activeField.type, formFieldsList.find((f) => f.type === activeField.type)?.name || t('PAGE_PROPS.CRUMB_QUESTION')) : t('PAGE_PROPS.CRUMB_QUESTION');
    const ending = formState.thankyouPage?.[activeThankYouPageComponent?.index ?? 0];
    const crumbs: InspectorCrumb[] = [{ level: 'form', label: t('PAGE_PROPS.CRUMB_FORM') }, { level: 'page', label: pageCrumbLabel(activeSlideComponent, ending) }, ...(activeFieldComponent?.id ? [{ level: 'question' as const, label: questionLabel }] : [])];

    const goTo = (target: InspectorLevel) => {
        if (target === 'question') return;
        setActiveFieldComponent(null);
        setActiveContainer(null);
        setPropertiesTab(target === 'page' ? 'page' : 'form');
    };

    return (
        <div className="flex h-full flex-col border-l" data-inspector>
            {activeSlideComponent?.id && <InspectorBreadcrumb crumbs={crumbs} current={level} onSelect={goTo} />}
            {activeFieldComponent?.id && <FieldSettings />}
            {!activeFieldComponent?.id && activeContainer && <LayoutContainerSettings />}
            {!activeFieldComponent?.id && !activeContainer && activeSlideComponent?.id && (
                <Tabs value={propertiesTab} onValueChange={(value) => setPropertiesTab(value as PropertiesTab)} className={cn('flex w-full flex-1 flex-col', propertiesTab === 'ai' && 'min-h-0')}>
                    <TabsList aria-label={t('PAGE_PROPS.SETTINGS_TABS')} className="mx-2 my-2 w-[calc(100%-16px)] shrink-0">
                        {TABS.map((tab) => (
                            <TabsTrigger key={tab.value} value={tab.value} className="w-full">
                                {t(tab.label)}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    <TabsContent value="page" className="mt-0">
                        <PagePropertiesTab />
                    </TabsContent>
                    <TabsContent value="form" className="mt-0">
                        <FormSettingsTab />
                    </TabsContent>
                    <TabsContent value="design">
                        <PageDesignTab />
                    </TabsContent>
                    <TabsContent value="ai" className="min-h-0 flex-1">
                        <AIChatTab />
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}
