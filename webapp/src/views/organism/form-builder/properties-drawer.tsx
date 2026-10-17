'use client';

import { useEffect } from 'react';

import { formFieldsList } from '@app/constants/form-fields';
import { InspectorLevel, inspectorLevel } from '@app/lib/hooks/use-inspector-escape';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@app/shadcn/components/ui/tabs';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { PropertiesTab, usePropertiesTab } from '@app/store/jotai/properties-tab';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';
import InspectorBreadcrumb, { InspectorCrumb } from '@app/views/molecules/form-builder/inspector-breadcrumb';
import FieldSettings from '@app/views/organism/field-settings';
import AIChatTab from '@app/views/organism/form-builder/ai-chat-tab';
import FormSettingsTab from '@app/views/organism/form-builder/form-settings-tab';
import PageDesignTab from '@app/views/organism/form-builder/page-design-tab';
import PagePropertiesTab from '@app/views/organism/form-builder/page-properties-tab';

/** What the Page crumb says for the selected page. */
export function pageCrumbLabel(slide: { id?: string; index?: number } | null | undefined): string {
    if (!slide) return 'Page';
    if (slide.id === 'welcome-page') return 'Welcome page';
    if (slide.id === 'thank-you-page') return 'Ending';
    return `Page ${(slide.index ?? 0) + 1}`;
}

const TABS: Array<{ value: PropertiesTab; label: string }> = [
    { value: 'page', label: 'Page' },
    { value: 'form', label: 'Form' },
    { value: 'design', label: 'Design' },
    { value: 'ai', label: 'AI' }
];

/**
 * The builder's inspector (right sidebar). A breadcrumb always says where
 * it is (Form › Page 2 › Question) and goes back up; Escape does the same
 * (lib/hooks/use-inspector-escape.ts). With a question selected it shows
 * that question's settings; otherwise the page and form settings, in tabs.
 */
export default function PropertiesDrawer({}: {}) {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { propertiesTab, setPropertiesTab } = usePropertiesTab();
    const { activeField } = useFormFieldsAtom();
    const standardForm = useAppSelector(selectForm);

    // Start-with-AI handoff: a pending prompt (stashed by the dashboard
    // dialog) opens the drawer on the AI tab; the tab itself consumes and
    // sends it.
    useEffect(() => {
        if (standardForm?.formId && typeof window !== 'undefined' && sessionStorage.getItem(`bc:ai-prompt:${standardForm.formId}`)) {
            setPropertiesTab('ai');
        }
    }, [standardForm?.formId]);

    const level = inspectorLevel(!!activeFieldComponent?.id, propertiesTab);
    const questionLabel = activeField ? extractTextfromJSON(activeField).trim() || formFieldsList.find((f) => f.type === activeField.type)?.name || 'Question' : 'Question';
    const crumbs: InspectorCrumb[] = [{ level: 'form', label: 'Form' }, { level: 'page', label: pageCrumbLabel(activeSlideComponent) }, ...(activeFieldComponent?.id ? [{ level: 'question' as const, label: questionLabel }] : [])];

    const goTo = (target: InspectorLevel) => {
        if (target === 'question') return;
        setActiveFieldComponent(null);
        setPropertiesTab(target === 'page' ? 'page' : 'form');
    };

    return (
        <div className="flex h-full flex-col border-l" data-inspector>
            {activeSlideComponent?.id && <InspectorBreadcrumb crumbs={crumbs} current={level} onSelect={goTo} />}
            {activeFieldComponent?.id && <FieldSettings />}
            {!activeFieldComponent?.id && activeSlideComponent?.id && (
                <Tabs value={propertiesTab} onValueChange={(value) => setPropertiesTab(value as PropertiesTab)} className={cn('flex w-full flex-1 flex-col', propertiesTab === 'ai' && 'min-h-0')}>
                    <TabsList aria-label="Settings" className="mx-2 my-2 w-[calc(100%-16px)] shrink-0">
                        {TABS.map((tab) => (
                            <TabsTrigger key={tab.value} value={tab.value} className="w-full">
                                {tab.label}
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
