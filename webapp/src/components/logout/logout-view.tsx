import { useRouter } from 'next/router';

import { Logout } from '@mui/icons-material';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import { useLazyGetLogoutQuery, useLazyGetStatusQuery } from '@app/store/auth/api';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import { useAppDispatch } from '@app/store/hooks';

export default function LogoutView(props: any) {
    const { closeModal } = useModal();

    const [trigger] = useLazyGetLogoutQuery();
    const [authTrigger] = useLazyGetStatusQuery();
    const dispatch = useAppDispatch();

    const workspace = props?.workspace;

    const router = useRouter();
    const handleLogout = async () => {
        await trigger().then(async () => {
            await authTrigger('status');
            if (!!workspace && !!workspace?.workspaceName && !!props?.isClientDomain) router.push(`/${workspace.workspaceName}`);
            else router.push('/login');
            dispatch(setAuth(initialAuthState));
            closeModal();
        });
    };

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-center gap-8 justify-between p-10">
                    <Logout className="text-6xl text-red-500" />
                    <h4 className="sh1 text-center">Are you sure you want to logout?</h4>

                    <div className="flex w-full gap-4 justify-end">
                        <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleLogout}>
                            Logout
                        </Button>
                        <Button variant="solid" color="gray" size="medium" className="!bg-black-500" onClick={closeModal}>
                            Cancel
                        </Button>
                    </div>
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={closeModal}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
