'use client'
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from "@app/views/organism/PropertiesDrawer";
import FieldSection from "@app/views/organism/FieldSection";
import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import {v4} from "uuid";
import {FieldTypes} from "@app/models/dtos/form";

export default function Home() {

    const {addSlide, formFields} = useFieldSelectorAtom();
    return (
        <main className="flex min-h-screen flex-col items-center justify-start bg-black-100">
            <Navbar/>
            <div className="flex h-body-content gap-10  w-full flex-row items-center">
                <div
                    id="slides-preview"
                    className="w-[400px] h-full bg-white"
                >
                    Slides Preview
                    <button className={'mx-4 p-2 bg-brand-400 text-white'} onClick={() => {
                        const fieldId = v4()
                        addSlide({
                            id: fieldId,
                            index: formFields.length,
                            type: FieldTypes.SLIDE,
                            properties:{
                                fields:[]
                            }
                        })
                    }}>Add Slide + </button>
                </div>
                {Array.isArray(formFields) && formFields.length ? formFields.map((slide, index) => {
                    return <FieldSection slide={slide} key={index}/>
                }) : <div className={'w-full'}></div>}
                <div
                    id="slide-element-properties"
                    className="w-[400px] self-stretch bg-white border-l-black-300"
                >
                    <PropertiesDrawer/>
                </div>
            </div>
        </main>
    );
}
