import Image from 'next/image';

import RectangleImage from '@app/assets/image/rectangle.png';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, setFormState, theme } = useFormState();
    const { activeSlide } = useFormFieldsAtom();

    return (
        <div
            className={`grid aspect-video h-min w-full grid-cols-2 bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
            style={{ background: theme?.accent }}
        >
            <div
                className={cn(
                    'grid-flow-col grid-cols-1 items-start justify-center gap-12 self-center px-12',
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
                <div className="flex w-full flex-col">
                    <h1 className="text-2xl font-semibold">Thank You!</h1>
                    {formState.thankYouMessage !== undefined ? (
                        <input
                            type="text"
                            placeholder="Your response has been successfully submitted"
                            value={formState.thankYouMessage}
                            className="border-0 px-0 text-base"
                            onChange={(e: any) =>
                                setFormState({
                                    ...formState,
                                    thankYouMessage: e.target.value
                                })
                            }
                        />
                    ) : (
                        <></>
                    )}
                </div>
                {formState.thankYouButtonText !== undefined ? (
                    <Button size={'medium'}>
                        {formState.thankYouButtonText || 'Try bettercollected'}
                    </Button>
                ) : (
                    <></>
                )}
            </div>
            <div
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
                    className={cn('h-full w-full')}
                    src={RectangleImage}
                    alt="LayoutImage"
                />
            </div>
        </div>
    );
};

export default ThankYouSlide;
