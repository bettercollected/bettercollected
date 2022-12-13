import dynamic from 'next/dynamic';

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
    const globalProps = (await globalServerProps(_context)).props;
    return {
        props: {
            ...globalProps
        }
    };
}
