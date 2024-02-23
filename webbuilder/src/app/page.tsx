'use client';

import cn from 'classnames';
import { PlusIcon } from 'lucide-react';
import { v4 } from 'uuid';

import { ThemeColor } from '@app/constants/theme';
import { FieldTypes } from '@app/models/dtos/form';
import { ButtonSize, ButtonVariant } from '@app/models/enums/button';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import useFieldSelectorAtom from '@app/store/jotai/fieldSelector';
import Button from '@app/views/atoms/Button';
import FieldSection from '@app/views/organism/FieldSection';
import Navbar from '@app/views/organism/Navbar';
import PropertiesDrawer from '@app/views/organism/PropertiesDrawer';

export default function Home() {
    const { addSlide, formFields } = useFieldSelectorAtom();

    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();

    const { setActiveFieldComponent } = useActiveFieldComponent();
    return (
        <main className="flex h-screen flex-col items-center justify-start bg-black-100">
            <Navbar />
            <div className="flex h-body-content w-full flex-row items-center gap-10">
                <div
                    id="slides-preview"
                    className="flex h-full w-[200px] flex-col gap-5 bg-white p-5"
                >
                    <div className="flex w-full items-center justify-between">
                        <span className="h4-new font-medium text-black-700">Pages</span>
                        <Button
                            variant={ButtonVariant.Secondary}
                            className="!p-2"
                            size={ButtonSize.Small}
                            onClick={() => {
                                const fieldId = v4();
                                addSlide({
                                    id: fieldId,
                                    index: formFields.length,
                                    type: FieldTypes.SLIDE,
                                    properties: {
                                        fields: [],
                                        theme: {
                                            primary: ThemeColor.primary,
                                            secondary: ThemeColor.secondary,
                                            tertiary: ThemeColor.tertiary,
                                            accent: ThemeColor.accent
                                        }
                                    }
                                });
                            }}
                            icon={<PlusIcon />}
                        ></Button>
                    </div>
                    {Array.isArray(formFields) && formFields.length ? (
                        formFields.map((slide, index) => {
                            return (
                                <div
                                    className={cn(
                                        'flex rounded-md border border-black-300 outline-none',
                                        activeSlideComponent?.id === slide.id &&
                                            '!border-pink-500'
                                    )}
                                    key={slide.id}
                                    tabIndex={0}
                                    onFocus={() => {
                                        setActiveSlideComponent({
                                            id: slide.id,
                                            index
                                        });
                                    }}
                                >
                                    <FieldSection slide={slide} disabled />
                                </div>
                            );
                        })
                    ) : (
                        <div className={'w-full'}></div>
                    )}
                </div>
                <div
                    className="flex h-full flex-1 flex-col items-center justify-center "
                    onClick={() => {
                        setActiveFieldComponent(null);
                    }}
                >
                    {activeSlideComponent?.id && (
                        <FieldSection slide={formFields[activeSlideComponent?.index]} />
                    )}
                    {!activeSlideComponent?.id && <div>Add a slide to start</div>}
                </div>
                <div
                    id="slide-element-properties"
                    className="h-full w-[200px] self-stretch overflow-auto border-l-black-300 bg-white"
                >
                    <PropertiesDrawer />
                </div>
            </div>
        </main>
    );
}
