import cn from 'classnames';

import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

import GreetingLayoutWrapper from '../Layout/GreetingLayoutWrapper';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();

    return (
        <GreetingLayoutWrapper disabled={disabled} greetingIndex={-10}>
            <div
                style={{
                    background: theme?.accent
                }}
                // TODO: Change this to apply layout from other layout
                className={cn(
                    'h-[${93.28 * 4}px] w-[${165.83 * 4}px] grid aspect-video h-min w-full grid-cols-1 bg-blue-100',
                    disabled ? 'pointer-events-none overflow-hidden' : '',
                    formState.welcomePage?.layout &&
                        formState.welcomePage?.layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-1'
                        : formState.welcomePage?.layout &&
                            formState.welcomePage?.layout ===
                                FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-0'
                          : ''
                )}
            >
                <div className={cn('flex flex-col items-center justify-center px-12')}>
                    <div className="flex flex-col items-start">
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
                                onChange={(e: any) =>
                                    setFormDescription(e.target.value)
                                }
                            />
                        ) : (
                            <></>
                        )}
                        <Button size={'medium'} className="mt-12">
                            {formState.buttonText || 'Start'}
                        </Button>
                    </div>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default WelcomeSlide;
