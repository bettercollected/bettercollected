"use client"
import {Switch} from "@app/shadcn/components/ui/switch";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import {useActiveSlideComponent} from "@app/store/jotai/activeBuilderComponent";

export default function PagePropertiesTab() {
    const {formFields, updateShowQuestionNumbers, activeSlide} = useFieldSelectorAtom();
    const {activeSlideComponent} = useActiveSlideComponent()

    return (
        <>
            <div className="mt-6 px-4 text-black-700 p2-new !font-medium mb-4">
                Layout
            </div>
            <div className="grid grid-cols-2 px-4 gap-2 pb-6 border-b">
                {
                    [1, 2, 3].map((item) => (
                        <div key={item} className="rounded-xl w-20 h-[50px] bg-gray-500">
                        </div>)
                    )}

            </div>
            <div className="mt-6 text-black-700 px-4 p2-new !font-medium mb-4">
                Settings
            </div>
            <div className="flex justify-between w-full px-4 items-center pb-4 border-b">
                <div className="text-xs text-black-700">
                    Question Numbers
                </div>
                <Switch checked={activeSlide?.properties?.showQuestionNumbers || false} onCheckedChange={(checked) => {
                    updateShowQuestionNumbers(activeSlide!.index, checked)
                }}/>
            </div>
            <div className="mt-6 text-black-700 p2-new px-4 !font-medium mb-6">
                Used Fields
            </div>
            <div className="flex flex-col mb-4 gap-6 px-4">
                {
                    (activeSlideComponent?.index !== undefined) && formFields[activeSlideComponent.index]?.properties?.fields?.map((field) => {
                        return <div key={field.id}
                                    className="flex justify-between gap-2 items-center text-xs text-black-700">
                            <div className="truncate">
                                {field?.title || "Untitled Question"}
                            </div>
                            <svg width="20" height="20" viewBox="0 0 20 20" fill="none"
                                 xmlns="http://www.w3.org/2000/svg">
                                <path d="M6 12.2695L14.0001 7.72927" stroke="#DBDBDB" strokeWidth="2"
                                      strokeLinecap="round"/>
                                <path d="M6 7.73047L14.0001 12.2707" stroke="#DBDBDB" strokeWidth="2"
                                      strokeLinecap="round"/>
                                <path d="M10 14L10 6" stroke="#DBDBDB" strokeWidth="2"
                                      strokeLinecap="round"/>
                            </svg>

                        </div>
                    })
                }
                {
                    (activeSlideComponent?.index !== undefined) && (!formFields[activeSlideComponent.index]?.properties?.fields || !formFields[activeSlideComponent.index]?.properties?.fields?.length) &&
                    <div className="text-xs text-black-700z">
                        No form fields in this page. Add elements to this page will be shown here
                    </div>
                }
            </div>
        </>
    )
}