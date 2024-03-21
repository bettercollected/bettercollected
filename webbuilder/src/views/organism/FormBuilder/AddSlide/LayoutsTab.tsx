import React from 'react';

import { v4 } from 'uuid';

import { FieldTypes } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import SlideLayoutBackgroundImage from '@app/views/atoms/Icons/SlideLayoutBackgroundImage';
import SlideLayoutLeftImage from '@app/views/atoms/Icons/SlideLayoutLeftImage';
import SlideLayoutNoImage from '@app/views/atoms/Icons/SlideLayoutNoImage';
import SlideLayoutRightImage from '@app/views/atoms/Icons/SlideLayoutRightImage';

const Layout = (props: {
    Icon: any;
    name: string;
    style?: FormSlideLayout;
    onClick?: (event?: React.MouseEvent<HTMLDivElement, MouseEvent>) => void;
}) => {
    return (
        <div
            className="cursor-pointer rounded-lg border border-transparent p-1 hover:border-pink-500"
            onClick={props.onClick}
        >
            <div className="mb-1 overflow-hidden rounded-xl border border-black-300 p-1 ">
                <props.Icon className="h-full w-full p-1" />
            </div>
            <div className="text-xs text-black-600">{props.name}</div>
        </div>
    );
};

export default function LayoutsTab({ closePopover }: { closePopover: () => void }) {
    const { formFields, addSlide } = useFormFieldsAtom();

    const addSlideofStyle = (style: FormSlideLayout) => {
        const fieldId = v4();
        addSlide({
            id: fieldId,
            index: formFields.length,
            type: FieldTypes.SLIDE,
            properties: {
                layout: style,
                fields: []
            }
        });
        closePopover();
    };

    return (
        <ScrollArea className="z-10 w-full overflow-auto pr-2">
            <div className="">
                <div className="mb-2 text-sm font-medium">Without Image</div>
                <div className="grid grid-cols-2 gap-4">
                    <Layout
                        Icon={SlideLayoutNoImage}
                        style={FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND}
                        name="No Image"
                        onClick={() => {
                            addSlideofStyle(
                                FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND
                            );
                        }}
                    />
                </div>
            </div>
            <div className=" mt-12">
                <div className="mb-2 text-sm font-medium">With Image</div>
                <div className="grid grid-cols-2 gap-4">
                    {[
                        {
                            style: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
                            Icon: SlideLayoutRightImage,
                            name: 'Right Image'
                        },
                        {
                            style: FormSlideLayout.TWO_COLUMN_IMAGE_LEFT,
                            Icon: SlideLayoutLeftImage,
                            name: 'Left Image'
                        },
                        {
                            style: FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND,
                            Icon: SlideLayoutBackgroundImage,
                            name: 'Fill Image'
                        }
                    ].map(
                        (item: { style: FormSlideLayout; Icon: any; name: string }) => (
                            <Layout
                                Icon={item.Icon}
                                style={item.style}
                                name={item.name}
                                onClick={() => {
                                    addSlideofStyle(item.style);
                                }}
                            />
                        )
                    )}
                </div>
            </div>
        </ScrollArea>
    );
}

const BlankLayout = () => {
    return (
        <svg
            width="168"
            height="94"
            viewBox="0 0 168 94"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
        >
            <g filter="url(#filter0_d_6436_17752)">
                <g clip-path="url(#clip0_6436_17752)">
                    <g filter="url(#filter1_d_6436_17752)">
                        <rect width="168" height="94.778" rx="1.36864" fill="white" />
                    </g>
                    <rect x="83" y="34" width="2" height="27" rx="1" fill="#FE3678" />
                    <rect
                        x="70.5"
                        y="48.5"
                        width="2"
                        height="27"
                        rx="1"
                        transform="rotate(-90 70.5 48.5)"
                        fill="#FE3678"
                    />
                </g>
            </g>
            <defs>
                <filter
                    id="filter0_d_6436_17752"
                    x="-1.02648"
                    y="-1.02648"
                    width="170.053"
                    height="96.053"
                    filterUnits="userSpaceOnUse"
                    colorInterpolationFilters="sRGB"
                >
                    <feFlood floodOpacity="0" result="BackgroundImageFix" />
                    <feColorMatrix
                        in="SourceAlpha"
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
                        result="hardAlpha"
                    />
                    <feOffset />
                    <feGaussianBlur stdDeviation="0.513238" />
                    <feComposite in2="hardAlpha" operator="out" />
                    <feColorMatrix
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.15 0"
                    />
                    <feBlend
                        mode="normal"
                        in2="BackgroundImageFix"
                        result="effect1_dropShadow_6436_17752"
                    />
                    <feBlend
                        mode="normal"
                        in="SourceGraphic"
                        in2="effect1_dropShadow_6436_17752"
                        result="shape"
                    />
                </filter>
                <filter
                    id="filter1_d_6436_17752"
                    x="-1.02648"
                    y="-1.02648"
                    width="170.053"
                    height="96.831"
                    filterUnits="userSpaceOnUse"
                    colorInterpolationFilters="sRGB"
                >
                    <feFlood floodOpacity="0" result="BackgroundImageFix" />
                    <feColorMatrix
                        in="SourceAlpha"
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
                        result="hardAlpha"
                    />
                    <feOffset />
                    <feGaussianBlur stdDeviation="0.513238" />
                    <feComposite in2="hardAlpha" operator="out" />
                    <feColorMatrix
                        type="matrix"
                        values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.15 0"
                    />
                    <feBlend
                        mode="normal"
                        in2="BackgroundImageFix"
                        result="effect1_dropShadow_6436_17752"
                    />
                    <feBlend
                        mode="normal"
                        in="SourceGraphic"
                        in2="effect1_dropShadow_6436_17752"
                        result="shape"
                    />
                </filter>
                <clipPath id="clip0_6436_17752">
                    <rect width="168" height="94" rx="1.36864" fill="white" />
                </clipPath>
            </defs>
        </svg>
    );
};
