import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import environments from '@app/configs/environments';
import { MediaLibrary, MediaLibraryDeleteRequestDto, MediaLibraryPostRequestDto, MediaLibraryRequestDto } from './type';

const MEDIA_LIBRARY_REDUCER_PATH = 'mediaLibraryApi';

const MEDIA_LIBRARY = 'MEDIA_LIBRARY';

export const mediaLibraryApi = createApi({
    reducerPath: MEDIA_LIBRARY_REDUCER_PATH,
    refetchOnReconnect: true,
    refetchOnFocus: true,
    refetchOnMountOrArgChange: true,
    tagTypes: [MEDIA_LIBRARY],
    baseQuery: fetchBaseQuery({
        baseUrl: environments.API_ENDPOINT_HOST + '/workspaces',
        credentials: 'include',
        prepareHeaders: (headers) => {
            return headers;
        }
    }),
    endpoints: (builder) => ({
        getWorkspaceMediaLibrary: builder.query<Array<MediaLibrary>, MediaLibraryRequestDto>({
            query: (data) => ({
                url: `/${data.workspace_id}/media?${data.media_query?`media_query=${data.media_query}`:''}`,
                method: 'GET',
                
               
            }),
            providesTags: [MEDIA_LIBRARY]
        }),
        addPhotoInWorkspaceMediaLibrary: builder.mutation<MediaLibrary, MediaLibraryPostRequestDto>({
            query: (data) => ({
                url: `/${data.workspace_id}/media`,
                method: 'POST',
                body: data.media
            }),
            invalidatesTags: [MEDIA_LIBRARY]
        }),
        deletePhotoFromWorkspaceMediaLibrary: builder.mutation<void, MediaLibraryDeleteRequestDto>({
            query: (data) => ({
                url: `/${data.workspace_id}/media/${data.media_id}`,
                method: 'DELETE'
            }),
            invalidatesTags: [MEDIA_LIBRARY]
        })
    })
});

export const { useGetWorkspaceMediaLibraryQuery, useAddPhotoInWorkspaceMediaLibraryMutation, useDeletePhotoFromWorkspaceMediaLibraryMutation, useLazyGetWorkspaceMediaLibraryQuery } = mediaLibraryApi;
