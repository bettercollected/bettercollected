import Image from 'next/image';

import RectangleImage from '@app/assets/image/rectangle.png';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

import GreetingLayoutWrapper from '../Layout/GreetingLayoutWrapper';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, setFormState, theme } = useFormState();

    return (
        <GreetingLayoutWrapper disabled={disabled} greetingIndex={-20}>
            <div
                // TODO: Change this to apply layout from other layout
                className={cn(
                    'h-[${93.28 * 4}px] w-[${165.83 * 4}px] grid aspect-video h-min w-full grid-cols-1 bg-blue-100',
                    disabled ? 'pointer-events-none overflow-hidden' : '',
                    formState.thankyouPage &&
                        formState.thankyouPage[0].layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-1'
                        : formState.thankyouPage &&
                            formState.thankyouPage[0].layout ===
                                FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-0'
                          : ''
                )}
                style={{ background: theme?.accent }}
            >
                <div className={cn('flex flex-col items-center justify-center px-12')}>
                    <div className="flex flex-col items-start">
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
                        {formState.thankYouButtonText !== undefined ? (
                            <Button size={'medium'} className='mt-4'>
                                {formState.thankYouButtonText || 'Try bettercollected'}
                            </Button>
                        ) : (
                            <></>
                        )}
                    </div>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default ThankYouSlide;
