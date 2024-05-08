import environments from '@app/configs/environments';
import { createApi } from 'unsplash-js';

const unsplash = createApi({
    accessKey: environments.UNSPLASH_ACCESS_KEY || ''
});

export async function getDefaultImageFromUnsplash(text: string) {
    return await unsplash.search.getPhotos({
        query: text,
        orientation: 'landscape',
        perPage: 100,
        page: 1
    });
}
