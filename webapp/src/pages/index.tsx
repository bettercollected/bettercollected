import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import globalServerProps from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';

const HomeContainer = dynamic(() => import('@app/containers/home/HomeContainer'), { ssr: false });
const DashboardContainer = dynamic(() => import('@app/containers/dashboard/DashboardContainer'), { ssr: false });

interface IHome extends IServerSideProps {}

const Home = ({ hasCustomDomain, workspace, workspaceId, ...props }: IHome) => {
    if (hasCustomDomain && workspace) return <DashboardContainer workspace={workspace} />;
    return <HomeContainer />;
};

export default Home;

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;
    const globalProps = (await globalServerProps(_context)).props;
    if (globalProps.hasCustomDomain) {
        return {
            props: { ...globalProps }
        };
    }
    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (user?.user?.roles?.includes('FORM_CREATOR')) {
            return {
                redirect: {
                    permanent: false,
                    destination: '/mydashboard'
                }
            };
        }
    } catch (e) {}
    return {
        props: {}
    };
}
