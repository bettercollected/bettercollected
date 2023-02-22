import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { checkHasCustomDomain } from '@app/utils/serverSidePropsUtils';

const LandingPage = dynamic(() => import('@app/containers/home/LandingPage'), { ssr: false });
const WorkspaceHomeContainer = dynamic(() => import('@app/containers/dashboard/WorkspaceHomeContainer'), { ssr: false });

interface IHome extends IServerSideProps {}

const Home = ({ hasCustomDomain, workspace }: IHome) => {
    if (hasCustomDomain && workspace) return <WorkspaceHomeContainer workspace={workspace} isCustomDomain={true} />;
    return <LandingPage />;
};

export default Home;

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;
    const hasCustomDomain = checkHasCustomDomain(_context);
    if (hasCustomDomain) {
        const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
        if (!globalProps?.workspace?.id) {
            return {
                notFound: true
            };
        }
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
        const user = (await userStatus?.json().catch((e: any) => e)) ?? null;
        if (user?.user?.roles?.includes('FORM_CREATOR')) {
            const userWorkspaceResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/mine`, config);
            const userWorkspace = (await userWorkspaceResponse?.json().catch((e: any) => e)) ?? null;
            if (!userWorkspace || userWorkspace.length < 1) {
                return {
                    redirect: {
                        permanent: false,
                        destination: `/setupWorkspace`
                    }
                };
            }
            return {
                redirect: {
                    permanent: false,
                    destination: `/${userWorkspace[0].workspaceName}/dashboard`
                }
            };
        }
    } catch (e) {}
    return {
        props: {}
    };
}
