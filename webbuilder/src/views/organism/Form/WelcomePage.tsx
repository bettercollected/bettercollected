import Image from 'next/image';
import Link from 'next/link';

import { Globe, Lock } from 'lucide-react';

import DemoImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useResponderState } from '@app/store/jotai/responderFormState';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';

export default function WelcomePage() {
    const { standardForm } = useStandardForm();
    const { nextSlide } = useResponderState();

    return (
        <div
            className="grid h-screen w-full grid-cols-2"
            style={{ background: standardForm.theme?.accent }}
        >
            <div className=" relative flex h-full flex-col justify-center px-20">
                <UserAvatarDropDown />

                <div className="text-[40px] font-bold leading-[48px]">
                    {standardForm.title}
                </div>
                {standardForm?.description && (
                    <div className="mt-4 text-black-700 ">
                        {standardForm?.description}
                    </div>
                )}
                <div className="mt-16 flex max-w-[421px] flex-col rounded-lg bg-white p-4">
                    <div className="flex items-center gap-2">
                        {standardForm?.settings?.requireVerifiedIdentity ? (
                            <>
                                <div className="rounded-full bg-red-100 p-[5px]">
                                    <Lock color="#EA400E" />
                                </div>
                                <span>This form is private</span>
                            </>
                        ) : (
                            <>
                                <div className="rounded-full bg-green-100 p-[5px]">
                                    <Globe color="#2DBB7F" />
                                </div>
                                <span>This form is public</span>
                            </>
                        )}
                    </div>
                    <div className="mt-2 text-xs text-black-700">
                        {standardForm?.settings?.requireVerifiedIdentity ? (
                            <>
                                The form you are trying to access is limited to certain
                                groups. Please verify your account to get access.
                            </>
                        ) : (
                            <>
                                The form you are trying to access is public, but you can
                                always sign in to view your response later.{' '}
                                <span>
                                    <Link href={'/login'} className="text-blue-500 ">
                                        {' '}
                                        Verify Account
                                    </Link>
                                </span>
                            </>
                        )}
                    </div>
                </div>
                <div className="mt-6">
                    <Button
                        style={{ background: standardForm.theme?.secondary }}
                        className="mt-20 rounded px-8 py-3"
                        size="medium"
                        onClick={() => {
                            if (!standardForm?.settings?.requireVerifiedIdentity) {
                                nextSlide();
                                return;
                            }
                        }}
                    >
                        {standardForm?.settings?.requireVerifiedIdentity
                            ? 'Verify Now'
                            : 'Start'}
                    </Button>
                </div>
            </div>
            <div className="relative h-full w-full">
                <Image
                    src={DemoImage}
                    alt="Demo Image"
                    fill
                    style={{
                        objectFit: 'cover'
                    }}
                    priority
                    sizes="(min-w: 0px) 100%"
                />
            </div>
        </div>
    );
}
