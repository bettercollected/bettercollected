import { atom, useAtom } from 'jotai';

interface HeaderImagesAtom {
    coverImage: File | null;
    logo: File | null;
}

const initHeaderImages={
    coverImage: null,
    logo : null
}

const headerImageAtom = atom<HeaderImagesAtom>(initHeaderImages);

export default function useFormBuilderAtom() {
    const [headerImages, setHeaderImages] = useAtom(headerImageAtom);

    const setCoverImage = (file :File | null)=>{
        setHeaderImages({
            ...headerImages,
            coverImage : file
        })
    }

    const setLogoImage = (file :File | null)=>{
        setHeaderImages({
            ...headerImages,
            logo : file
        })
    }

    const resetImages = ()=>{
        setHeaderImages(initHeaderImages)
    }

    return { headerImages, setCoverImage, setLogoImage, resetImages };
}
