import Image from 'next/image';

import cn from 'classnames';

import RectangleImage from '@app/assets/image/rectangle.png';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();

    const { activeSlide } = useFormFieldsAtom();
    const { nextSlide } = useFormResponse();

    return (
        <div
            style={{
                background: theme?.accent
            }}
            // TODO: Change this to apply layout from other layout
            className={`grid aspect-video h-min w-full grid-cols-1 bg-blue-100 h-[${93.28 * 4}px] w-[${165.83 * 4}px] ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
        >
            <div
                className={cn(
                    'grid-flow-col grid-cols-1 items-center justify-center gap-12 self-center px-12',
                    activeSlide &&
                        activeSlide.properties?.layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-1'
                        : activeSlide &&
                            activeSlide.properties?.layout ===
                                FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-0'
                          : ''
                )}
            >
                <div className="flex flex-col">
                    <input
                        type="text"
                        placeholder="Form Title"
                        className="border-0 px-0 text-[40px] font-bold"
                        value={formState.welcomeTitle}
                        onChange={(event) => {
                            setWelcomeTitle(event.target.value);
                        }}
                    />
                    {formState.description !== undefined ? (
                        <input
                            type="text"
                            placeholder="Add description"
                            value={formState.description}
                            className="border-0 px-0 text-base"
                            onChange={(e: any) => setFormDescription(e.target.value)}
                        />
                    ) : (
                        <></>
                    )}
                </div>
                <Button size={'medium'} onClick={() => nextSlide()}>
                    {formState.buttonText || 'Start'}
                </Button>
            </div>
            {/* <div
                className={cn(
                    'grid-cols-1',
                    activeSlide &&
                        activeSlide.properties?.layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-0'
                        : activeSlide &&
                            activeSlide.properties?.layout ===
                                FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-1'
                          : ''
                )}
            >
                <Image
                    objectFit="cover"
                    className={cn(
                        'h-full w-full',
                        activeSlide &&
                            activeSlide.properties?.layout ===
                                FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                            ? 'order-0'
                            : activeSlide &&
                                activeSlide.properties?.layout ===
                                    FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                              ? 'order-1'
                              : ''
                    )}
                    src={RectangleImage}
                    alt="LayoutImage"
                />
            </div> */}
        </div>
    );
};

export default WelcomeSlide;
