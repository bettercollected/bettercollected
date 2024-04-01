import cn from 'classnames';

import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

import GreetingLayoutWrapper from '../Layout/GreetingLayoutWrapper';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();

    return (
        <GreetingLayoutWrapper theme={theme} disabled={disabled} greetingIndex={-10}>
            <div
                className={cn(
                    'flex h-full flex-col items-center justify-center bg-transparent'
                )}
            >
                <div className={cn('flex w-full max-w-[800px] flex-col items-start')}>
                    <input
                        type="text"
                        placeholder="Form Title"
                        className="mb-4 w-min border-0 px-0 py-0 text-[40px] font-bold"
                        value={formState.welcomePage?.title}
                        onChange={(event) => {
                            setWelcomeTitle(event.target.value);
                        }}
                    />
                    {formState.description !== undefined ? (
                        <input
                            type="text"
                            placeholder="Add description"
                            value={formState.description}
                            className="border-0 px-0 py-0 text-base"
                            onChange={(e: any) => setFormDescription(e.target.value)}
                        />
                    ) : (
                        <></>
                    )}
                    <Button
                        size={'medium'}
                        className="z-10 mt-12 rounded px-8 py-3"
                        style={{ background: theme?.secondary }}
                    >
                        {formState.welcomePage?.buttonText || 'Start'}
                    </Button>
                </div>
            </div>
        </GreetingLayoutWrapper>
    );
};

export default WelcomeSlide;
