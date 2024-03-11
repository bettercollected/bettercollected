import Image from 'next/image';

import RectangleImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { useFormState } from '@app/store/jotai/form';

const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    const { theme, formState, setFormDescription, setWelcomeTitle } = useFormState();
    return (
        <div
            style={{
                background: theme?.accent
            }}
            className={`flex aspect-video h-min w-full bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
        >
            <div className=" flex basis-1/2 flex-col items-start justify-center gap-12 px-12">
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
                <Button size={'medium'}>{formState.buttonText || 'Start'}</Button>
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

export default WelcomeSlide;
