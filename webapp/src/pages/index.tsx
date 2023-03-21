import { GetServerSidePropsContext } from 'next';
import dynamic from 'next/dynamic';

import environments from '@app/configs/environments';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { checkHasAdminDomain, checkHasClientDomain, checkHasCustomDomain } from '@app/utils/serverSidePropsUtils';

const WorkspaceHomeContainer = dynamic(() => import('@app/containers/dashboard/WorkspaceHomeContainer'), { ssr: false });

interface IHome extends IServerSideProps {}

const Home = ({ hasCustomDomain, workspace }: IHome) => {
    if (hasCustomDomain && workspace) return <WorkspaceHomeContainer workspace={workspace} isCustomDomain={true} />;
    return <></>;
};

export default Home;

export async function getServerSideProps(_context: GetServerSidePropsContext) {
    const hasAdminDomain = checkHasAdminDomain(_context);
    const hasClientDomain = checkHasClientDomain(_context);

    const scheme = _context.req.headers?.referer?.includes('https://') ? 'https://' : 'http://';
    if (!hasAdminDomain && !hasClientDomain) {
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

    if (hasClientDomain) {
        return {
            redirect: {
                permanent: false,
                destination: `${scheme}${environments.ADMIN_HOST}`
            }
        };
    }

    return {
        redirect: {
            permanent: false,
            destination: `/login`
        }
    };
}
