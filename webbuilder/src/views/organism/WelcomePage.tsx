import Image from 'next/image';

import cn from 'classnames';

import RectangleImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

const WelcomeSlide = ({
    disabled,
    layout
}: {
    disabled?: boolean;
    layout: 'two-column-right' | 'two-column-left';
}) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();
    const { nextSlide } = useFormResponse();
    return (
        <div
            style={{
                background: theme?.accent
            }}
            className={`grid aspect-video h-min w-full grid-cols-2 bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
        >
            <div
                className={cn(
                    'grid-flow-col grid-cols-1 items-center justify-center gap-12 self-center px-12',
                    layout === 'two-column-right'
                        ? 'order-1'
                        : layout === 'two-column-left'
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
            <div
                className={cn(
                    'grid-cols-1',
                    layout === 'two-column-right'
                        ? 'order-0'
                        : layout === 'two-column-left'
                          ? 'order-1'
                          : ''
                )}
            >
                <Image
                    objectFit="cover"
                    className={cn(
                        'h-full w-full',
                        layout === 'two-column-right'
                            ? 'order-0'
                            : layout === 'two-column-left'
                              ? 'order-1'
                              : ''
                    )}
                    src={RectangleImage}
                    alt="LayoutImage"
                />
            </div>
        </div>
    );
};

export default WelcomeSlide;
