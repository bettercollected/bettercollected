import { useRouter } from 'next/router';

import environments from '@app/configs/environments';
import { setBuilderState } from '@app/store/form-builder/actions';
import { initBuilderState } from '@app/store/form-builder/builderSlice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useCreateFormMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import HeaderModalWrapper from '../ModalWrappers/HeaderModalWrapper';

export default function BuilderVersionSelectorModal() {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [postCreateForm, { isLoading: posting }] = useCreateFormMutation();

    const dispatch = useAppDispatch();

    const createV1Form = async () => {
        const formData = new FormData();
        const postReq: any = {};
        postReq.title = initBuilderState.title;
        postReq.description = initBuilderState.description;
        postReq.fields = Object.values(initBuilderState.fields);
        postReq.buttonText = initBuilderState.buttonText;
        postReq.consent = [];
        postReq.settings = {};
        formData.append('form_body', JSON.stringify(postReq));
        const apiObj: any = { workspaceId: workspace.id, body: formData };
        const response: any = await postCreateForm(apiObj);

        if (response?.data) {
            router.push(`/${workspace?.workspaceName}/dashboard/forms/v1/${response?.data?.formId}/edit`);
            dispatch(setBuilderState({ isFormDirty: false }));
        }
    };

    const createV2Form = () => {
        router.push(`${environments.HTTP_SCHEME}${environments.V2_BUILDER_DOMAIN}/${workspace?.workspaceName}/dashboard/form/create`);
    };

    return (
        <HeaderModalWrapper headerTitle="Form type">
            <div className="flex flex-row gap-6">
                <div onClick={createV1Form} className="hover:bg-black-100 flex w-[130px] cursor-pointer flex-col rounded-lg pb-4">
                    <div>
                        <svg width="133" height="130" viewBox="0 0 133 130" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <rect x="26.5" y="15.5" width="79" height="99" rx="7.5" fill="white" />
                            <rect x="26.5" y="15.5" width="79" height="99" rx="7.5" stroke="#E2E2E2" />
                            <rect x="41" y="44" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="44" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="65" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="86" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="52" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="73" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="41" y="94" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <path d="M27 19C27 16.7909 28.7909 15 31 15H102C104.209 15 106 16.7909 106 19V31H27V19Z" fill="#D9D9D9" />
                            <rect x="41.5" y="23.5" width="14" height="14" rx="3.5" fill="#D9D9D9" stroke="white" />
                        </svg>
                    </div>
                    <div className="p2-new text-black-700 text-center">Single Page</div>
                </div>
                <div onClick={createV2Form} className="hover:bg-black-100 flex w-[130px] cursor-pointer flex-col items-center rounded-lg pb-4">
                    <div>
                        <svg width="115" height="130" viewBox="0 0 115 130" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <rect x="12.5" y="28.5" width="79" height="65" rx="7.5" fill="white" />
                            <rect x="12.5" y="28.5" width="79" height="65" rx="7.5" stroke="#E2E2E2" />
                            <rect x="19" y="37" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="19" y="61" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <path d="M53 36C53 33.7909 54.7909 32 57 32H83C85.2091 32 87 33.7909 87 36V86C87 88.2091 85.2091 90 83 90H57C54.7909 90 53 88.2091 53 86V36Z" fill="#D9D9D9" />
                            <rect x="19" y="45" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="19" y="69" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="22.5" y="36.5" width="79" height="65" rx="7.5" fill="white" />
                            <rect x="22.5" y="36.5" width="79" height="65" rx="7.5" stroke="#E2E2E2" />
                            <rect x="29" y="45" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="29" y="69" width="23" height="5" rx="2.5" fill="#D9D9D9" />
                            <path d="M63 44C63 41.7909 64.7909 40 67 40H93C95.2091 40 97 41.7909 97 44V94C97 96.2091 95.2091 98 93 98H67C64.7909 98 63 96.2091 63 94V44Z" fill="#D9D9D9" />
                            <rect x="29" y="53" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                            <rect x="29" y="77" width="30" height="5" rx="2.5" fill="#D9D9D9" />
                        </svg>
                    </div>
                    <div className="p2-new text-black-700 text-center">Slide</div>
                </div>
            </div>
        </HeaderModalWrapper>
    );
}
