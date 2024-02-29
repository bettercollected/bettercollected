import Image from 'next/image';

import RectangleImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    const { formState, setFormState, theme } = useFormState();
    return (
        <div
            className={`flex aspect-video h-min w-full bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
            style={{ background: theme?.accent }}
        >
            <div className=" flex basis-1/2 flex-col items-start justify-center gap-12 px-12">
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
            <Image
                objectFit="cover"
                className="basis-1/2"
                src={RectangleImage}
                alt="LayoutImage"
            />
        </div>
    );
};

export default ThankYouSlide;
