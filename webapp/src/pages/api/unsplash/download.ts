import { NextApiRequest, NextApiResponse } from 'next';
import { createApi } from 'unsplash-js';

const unsplashAccessKey = process.env.UNSPLASH_ACCESS_KEY || '';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const photo: any = JSON.parse(req.body);
    try {
        const unsplash = createApi({ accessKey: unsplashAccessKey });
        const response = await unsplash.photos.trackDownload({ downloadLocation: photo.links.download_location });
        return res.status(200).json(response);
    } catch (e) {
        console.log(e);
        return res.status(500).json({ error: e });
    }
}
