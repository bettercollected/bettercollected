'use client'

import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from "@app/views/organism/PropertiesDrawer";
import FieldSection from "@app/views/organism/FieldSection";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import { v4 } from "uuid";
import { FieldTypes } from "@app/models/dtos/form";
import Button from "@app/views/atoms/Button";
import { ButtonVariant } from "@app/models/enums/button";
import { useActiveSlideComponent } from "@app/store/jotai/activeBuilderComponent";
import cn from "classnames";

export default function Home() {

    const { addSlide, formFields } = useFieldSelectorAtom();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent()
    return (
        <main className="flex min-h-screen flex-col items-center justify-start bg-black-100">
            <Navbar />
            <div className="flex h-body-content gap-10 w-full flex-row items-center">
                <div
                    id="slides-preview"
                    className="w-[400px] h-full flex flex-col gap-5 bg-white p-5"
                >
                    <div className="w-full justify-between flex">
                        <span className="font-medium h4-new text-black-700">
                            Slides Preview
                        </span>
                        <Button variant={ButtonVariant.Primary} className={' p-2 bg-brand-400 text-white'}
                            onClick={() => {
                                const fieldId = v4()
                                addSlide({
                                    id: fieldId,
                                    index: formFields.length,
                                    type: FieldTypes.SLIDE,
                                    properties: {
                                        fields: []
                                    }
                                })
                            }}>Add Slide +
                        </Button>
                    </div>
                    {Array.isArray(formFields) && formFields.length ? formFields.map((slide, index) => {
                        return (
                            <div
                                className={cn("flex border border-black-300 rounded-md outline-none", activeSlideComponent?.id === slide.id && "!border-pink-500")}
                                key={slide.id} tabIndex={0} onFocus={() => {
                                    setActiveSlideComponent({ id: slide.id, index })
                                }}>
                                <FieldSection slide={slide} disabled />
                            </div>)
                    }) : <div className={'w-full'}></div>}
                </div>
                <div className="flex-1">
                    {
                        activeSlideComponent?.id ?
                            <FieldSection slide={formFields[activeSlideComponent?.index]} /> : <div>
                                Add a slide to start
                            </div>
                    }
                    {/* {
                        !activeSlideComponent?.id && 
                    } */}
                </div>
                <div
                    id="slide-element-properties"
                    className="w-[400px] self-stretch bg-white border-l-black-300"
                >
                    <PropertiesDrawer />
                </div>
            </div>
        </main>
    );
}
