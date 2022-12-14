import { useEffect, useMemo } from 'react';

import { useModal } from '@app/components/modal-views/context';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import useUserAuth from '@app/lib/hooks/use-authuser';
import { authApi, useGetStatusQuery } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';

export default function CreatorDashboard() {
    const { openModal } = useModal();

    const { user, isLoading } = useUserAuth();

    if (isLoading) return <FullScreenLoader />;

    const email = user.data.payload.content.user.sub;

    const handleImportForms = () => {
        openModal('IMPORT_FORMS_VIEW');
    };

    const Header = () => (
        <div className="flex justify-between items-center mb-10">
            <div className="flex flex-col">
                <h1 className="font-extrabold text-3xl">Hello {email.replaceAll('@gmail.com', '')}!</h1>
                <p className="text-gray-600">Here you have the summary of the week</p>
            </div>

            <Button variant="solid" className="ml-3 !px-3 !rounded-xl !bg-blue-500" onClick={handleImportForms}>
                Import Forms
            </Button>
        </div>
    );

    // UI for forms
    const MyRecentForms = () => {
        return (
            <div>
                <h1 className="font-semibold text-2xl">My Recent Forms</h1>
            </div>
        );
    };

    return (
        <Layout>
            <Header />
            <MyRecentForms />
        </Layout>
    );
}

// export const getServerSideProps = async (context: any) => {
//     const cookies = context.req.headers.cookie;
//     console.log('cookies:', cookies);

//     return {
//         props: {}
//     };
// };
