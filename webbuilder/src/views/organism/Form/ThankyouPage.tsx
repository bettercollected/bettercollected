import Image from 'next/image';
import Link from 'next/link';

import DemoImage from '@app/assets/image/rectangle.png';
import { ButtonSize } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { standardForm } = useStandardForm();
    return (
        <div
            className="grid h-screen w-full grid-cols-1"
            style={{ background: standardForm.theme?.accent }}
        >
            <div className=" flex h-full flex-col justify-center px-4  lg:px-20">
                <UserAvatarDropDown disabled />

                <div className="px-4  lg:px-20">
                    <div className="flex">
                        <span className="text-[40px] font-bold leading-[48px]">
                            Thank You! 🎉
                        </span>
                    </div>
                    <div className="p2-new mt-4 text-black-700">
                        Your response is successfully submitted anonymously.
                    </div>
                    <Button
                        style={{ background: standardForm.theme?.secondary }}
                        className="mt-14"
                        size={ButtonSize.Medium}
                    >
                        <Link
                            href={
                                isPreviewMode
                                    ? ''
                                    : standardForm?.buttonLink ||
                                      'https://bettercollected.com'
                            }
                            target="_blank"
                            referrerPolicy="no-referrer"
                        >
                            {standardForm?.buttonText || 'Try Bettercollected'}
                        </Link>
                    </Button>
                    <div className="p2-new mt-10 rounded-lg bg-white p-4">
                        <div className=" text-black-700">
                            You can view or request deletion of this response.
                        </div>
                        <div>
                            <Link
                                href={isPreviewMode ? '' : 'https://youtube.com'}
                                className="text-blue-500"
                            >
                                See all your submissions
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
