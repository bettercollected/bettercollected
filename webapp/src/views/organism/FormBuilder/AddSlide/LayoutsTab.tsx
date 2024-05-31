import React from 'react';

import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import SlideLayoutBackgroundImage from '@app/views/atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '@app/views/atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '@app/views/atoms/Icons/SlideLayoutNoImage';
import { SlideLayoutNoImageLeftAlign } from '@app/views/atoms/Icons/SlideLayoutNoImageLeftAlign';
import SlideLayoutRightImage from '@app/views/atoms/Icons/SlideLayoutRightImage';
import Image from 'next/image';
import globalConstants from '@app/constants/global';
import { useAuthAtom } from '@app/store/jotai/auth';

const Layout = (props: { Icon: any; name: string; image: string; style?: FormSlideLayout; onClick?: (event?: React.MouseEvent<HTMLDivElement, MouseEvent>) => void }) => {
    const { authState } = useAuthAtom();
    return (
        <button data-umami-event={`${props.name} Button`} data-umami-event-email={authState.email}>
            <div className="cursor-pointer rounded-lg border border-transparent" onClick={props.onClick}>
                <div
                    className="border-black-300 relative mb-1 overflow-hidden rounded-xl border "
                    style={{
                        width: '168px',
                        height: '94px'
                    }}
                >
                    <Image src={props.image} alt={props.name} fill sizes="(min-width 100px) 100%" />
                    <div className="absolute inset-0 z-10 bg-transparent transition-all hover:bg-[#00000026]"></div>
                </div>
                <div className="text-black-600 text-xs">{props.name}</div>
            </div>
        </button>
    );
};

export default function LayoutsTab({ closePopover }: { closePopover: () => void }) {
    const { formFields, addSlide } = useFormFieldsAtom();
    const { setActiveSlideComponent, activeSlideComponent } = useActiveSlideComponent();
    const { authState } = useAuthAtom();

    const addSlideOfStyle = (style: FormSlideLayout, blank: boolean = false) => {
        const fieldId = v4();
        const newSlideIndex = (activeSlideComponent?.index || 0) < 0 ? formFields.length : (activeSlideComponent?.index || 0) + 1;
        addSlide(
            {
                id: fieldId,
                index: formFields.length,
                type: FieldTypes.SLIDE,
                properties: {
                    layout: style,
                    fields: [
                        ...(blank
                            ? []
                            : [
                                  {
                                      id: v4(),
                                      index: 0,
                                      type: FieldTypes.SHORT_TEXT,
                                      value: 'Enter Question',
                                      properties: {
                                          placeholder: 'Answer'
                                      }
                                  }
                              ])
                    ]
                },
                imageUrl: globalConstants.defaultImage
            },
            newSlideIndex
        );
        setActiveSlideComponent({ id: fieldId, index: newSlideIndex });
        window.setTimeout(function () {
            const element = document.getElementById(fieldId);
            element?.scrollIntoView({
                behavior: 'smooth',
                block: 'end'
            });
        }, 500);
        closePopover();
    };

    return (
        <ScrollArea className="z-10 h-[495px] w-full overflow-auto pr-4">
            <div className="">
                <div className="mb-2 text-sm font-medium">Blank</div>
                <button data-umami-event={'Add Blank Page Button'} data-umami-event-email={authState.email}>
                    <div
                        className="hover:bg-black-200 border-black-200 w-fit cursor-pointer rounded-lg border px-[70px] py-8 transition-all"
                        onClick={() => {
                            addSlideOfStyle(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN, true);
                        }}
                    >
                        <BlankLayout />
                    </div>
                </button>
                <div className="text-black-600 mt-2 text-xs">Blank</div>
            </div>
            <div className="mt-12">
                <div className="mb-2 text-sm font-medium">Without Image</div>
                <div className="grid grid-cols-2 gap-4">
                    {[
                        {
                            style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN,
                            Icon: SlideLayoutNoImageLeftAlign,
                            name: 'Left Align',
                            image: '/images/Left.png'
                        },
                        {
                            style: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND,
                            Icon: SlideLayoutNoImage,
                            name: 'Center Align',
                            image: '/images/center.png'
                        }
                    ].map((item: { style: FormSlideLayout; Icon: any; name: string; image: string }) => (
                        <Layout
                            key={item.name}
                            Icon={item.Icon}
                            style={item.style}
                            image={item.image}
                            name={item.name}
                            onClick={() => {
                                addSlideOfStyle(item.style);
                            }}
                        />
                    ))}
                </div>
            </div>
            <div className=" mt-12">
                <div className="mb-2 text-sm font-medium">With Image</div>
                <div className="grid grid-cols-2 gap-4">
                    {[
                        {
                            style: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                            Icon: SlideLayoutRightImage,
                            name: 'Right Image',
                            image: '/images/right-image.png'
                        },
                        {
                            style: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT,
                            Icon: SlideLayoutLeftImage,
                            name: 'Left Image',
                            image: '/images/left-image.png'
                        },
                        {
                            style: FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND,
                            Icon: SlideLayoutBackgroundImage,
                            name: 'Fill Image',
                            image: '/images/image.png'
                        }
                    ].map((item: { style: FormSlideLayout; Icon: any; name: string; image: string }) => (
                        <Layout
                            key={item.name}
                            Icon={item.Icon}
                            style={item.style}
                            image={item.image}
                            name={item.name}
                            onClick={() => {
                                addSlideOfStyle(item.style);
                            }}
                        />
                    ))}
                </div>
            </div>
        </ScrollArea>
    );
}

const BlankLayout = () => {
    return (
        <svg width="28" height="27" viewBox="0 0 28 27" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="13" width="2" height="27" rx="1" fill="#FE3678" />
            <rect x="0.5" y="14.5" width="2" height="27" rx="1" transform="rotate(-90 0.5 14.5)" fill="#FE3678" />
        </svg>
    );
};
