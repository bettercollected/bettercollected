import _ from 'lodash';

import { SyncProblem } from '@mui/icons-material';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';

interface ImportErrorViewProps {
    provider: string;
}

export default function ImportErrorView({ provider }: ImportErrorViewProps) {
    const { closeModal } = useModal();
    return (
        <div className="text-sm relative py-10 px-10 flex items-center justify-center flex-col space-y-5 min-w-screen md:min-w-[400px] p-4 rounded-md shadow-md bg-white">
            <div onClick={() => closeModal()} className="border-[1.5px] absolute right-5 top-5 border-gray-200 hover:shadow hover:text-black cursor-pointer rounded-full p-3">
                <Close className="cursor-pointer text-gray-600 hover:text-black" />
            </div>
            <SyncProblem className="w-[100px] h-[110px] text-red-600" />
            <h2 className="text-gray-700 text-xl text-center">
                You have not yet authorized or <br /> Your {_.capitalize(provider)} authorization has expired
            </h2>
            <h6 className="text-gray-500 text-center">
                Please click the link below <br /> to authorize {_.capitalize(provider)}.
            </h6>
            <a className="ml-3 items-center flex justify-center !rounded-xl px-8 py-3 text-white !bg-blue-500" href={`${environments.API_ENDPOINT_HOST}/auth/${provider}/oauth?creator=true`}>
                Authorize {_.capitalize(provider)}
            </a>
        </div>
    );
}
