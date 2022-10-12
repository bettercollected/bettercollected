/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-12
 * Time: 16:17
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import {Carousel} from 'react-responsive-carousel';

export default function LocalCarousel(ImagesArray: Array<any>) {
    return (
        <Carousel autoPlay={true} showThumbs={false} interval={2000}>
            {ImagesArray.map((image, index) => (
                <div key={index} className={"h-screen"}>
                    <img src={image.src} alt={image.name}/>
                </div>
            ))}
        </Carousel>
    )
}