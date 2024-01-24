import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import { resetServerContext } from 'react-beautiful-dnd';

import environments from '@app/configs/environments';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { checkHasAdminDomain, checkHasCustomDomain, checkIfUserIsAuthorizedToViewPage, checkIfUserIsAuthorizedToViewWorkspaceSettingsPage, getRequestHost, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export async function getGlobalServerSidePropsByDomain({ locale, ..._context }: any): Promise<{
    props: IServerSideProps;
}> {
    const domain = getRequestHost(_context);
    const hasCustomDomain = checkHasCustomDomain(_context);
    let workspaceId = '';
    let workspace = null;

    if (!hasCustomDomain) {
        return {
            props: {
                ...(await serverSideTranslations(locale, ['common'], null, ['en', 'nl'])),
                hasCustomDomain,
                workspaceId,
                workspace
            }
        };
    }
    try {
        const workspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?custom_domain=${domain}`).catch((e) => e);
        workspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
        workspaceId = workspace?.id || null;
    } catch (e) {}

    return {
        props: {
            ...(await serverSideTranslations(locale, ['common'], null, ['en', 'nl'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}

export async function getGlobalServerSidePropsByWorkspaceName({ locale, ..._context }: any): Promise<
    | {
          props: IServerSideProps;
      }
    | any
> {
    const hasCustomDomain = checkHasCustomDomain(_context);
    let workspaceId = '';
    let workspace = null;
    const { workspace_name } = _context.params;

    const config = getServerSideAuthHeaderConfig(_context);

    if (!workspace_name) {
        return {
            props: {
                ...(await serverSideTranslations(locale, ['common', 'builder'], null, ['en', 'nl'])),
                hasCustomDomain,
                workspaceId,
                workspace
            }
        };
    }
    try {
        const workspaceResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces?workspace_name=${workspace_name}`, config).catch((e) => e);
        workspace = (await workspaceResponse?.json().catch((e: any) => e)) ?? null;
        workspaceId = workspace.id;
    } catch (e) {}
    return {
        props: {
            ...(await serverSideTranslations(locale, ['common', 'builder'], null, ['en', 'nl'])),
            hasCustomDomain,
            workspaceId,
            workspace
        }
    };
}

export async function getAuthUserPropsWithWorkspace(_context: any) {
    // Resets and enables the drag and drop functionality without an issue
    resetServerContext();
    const hasAdminDomain = checkHasAdminDomain(getRequestHost(_context));
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;
    if (!hasAdminDomain) {
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    }
    if (!globalProps?.workspace?.id) {
        return {
            notFound: true
        };
    }
    if (!(await checkIfUserIsAuthorizedToViewPage(_context, globalProps.workspace)))
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    return {
        props: {
            ...globalProps
        }
    };
}

export async function getServerSidePropsForWorkspaceAdmin(_context: any) {
    const hasAdminDomain = checkHasAdminDomain(getRequestHost(_context));

    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    const locale = globalProps['_nextI18Next']['initialLocale'] === 'en' ? '' : `${globalProps['_nextI18Next']['initialLocale']}/`;

    if (!hasAdminDomain) {
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    }

    if (!globalProps?.workspace?.id) {
        return {
            notFound: true
        };
    }
    if (!(await checkIfUserIsAuthorizedToViewWorkspaceSettingsPage(_context, globalProps.workspace)))
        return {
            redirect: {
                permanent: false,
                destination: `/${locale}`
            }
        };
    return {
        props: {
            ...globalProps
        }
    };
}

export async function getServerSidePropsForDashboardFormPage(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    if (!props.props) {
        return props;
    }
    const globalProps = props.props;
    const { form_id } = _context.query;
    let form = null;
    const config = getServerSideAuthHeaderConfig(_context);
    try {
        const formResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspace?.id}/forms/${form_id}`, config);
        form = (await formResponse?.json().catch((e: any) => e)) ?? null;
        if (!form) {
            return {
                notFound: true
            };
        }

        return {
            props: {
                formId: form_id,
                ...globalProps,
                form
            }
        };
    } catch (e) {
        return {
            props: {
                error: true
            }
        };
    }
}