import Router from 'next/router';

import { Close } from '@app/components/icons/close';
import Image from '@app/components/ui/image';
import { useLazyGetLogoutQuery } from '@app/store/auth/api';

import { useModal } from '../modal-views/context';
import Button from '../ui/button';

export default function LogoutView(props: any) {
    const { closeModal } = useModal();

    const [trigger] = useLazyGetLogoutQuery();

    const handleLogout = async () => {
        await trigger();
        closeModal();
        Router.push('/');
    };

    function DialogBox() {
        return (
            <>
                <h5 className="text-lg font-semibold leading-normal text-left ">Are you sure to logout?</h5>
                <div className="flex w-full gap-4 justify-between">
                    <Button variant="solid" className="!rounded-xl !m-0 !bg-blue-500" onClick={handleLogout}>
                        Logout
                    </Button>
                    <Button variant="transparent" className="!rounded-xl !m-0 !border-gray border-[1px] !border-solid" onClick={() => closeModal()}>
                        Cancel
                    </Button>
                </div>
            </>
        );
    }

    function ImageRenderer() {
        return (
            <div>
                <Image src="/otp.svg" width="150px" height="150px" alt="OTP Image" />
            </div>
        );
    }

    function LoginContainer() {
        const { closeModal } = useModal();

        return (
            <div className=" relative m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-110">
                <div className=" relative flex flex-col  items-center gap-8 justify-between p-10">
                    <ImageRenderer />
                    <DialogBox />
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        );

        // return <DialogBox/>
    }

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <LoginContainer />
            {/* <LogoutView /> */}
        </div>
    );
}
