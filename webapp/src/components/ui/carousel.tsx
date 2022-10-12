/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-12
 * Time: 16:17
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import {Carousel} from 'react-responsive-carousel';
import PropTypes, {any} from "prop-types";
import Image from "next/image";

function LocalCarousel({ ImagesArray }:any) {
    return (
        <div className="min-h-screen md:h-auto md:w-3/5">
            <Carousel autoPlay={true} showThumbs={false} interval={2000}>
                {ImagesArray.map((image:any, index:number) => (
                    <div key={index} className={"h-screen"}>
                        <Image src={image} alt={image.name}/>
                    </div>
                ))}
            </Carousel>
        </div>
    )
}

LocalCarousel.propTypes = {
    ImagesArray: PropTypes.arrayOf(any)
}

LocalCarousel.defaultProps = {
    ImagesArray: []
}

export default LocalCarousel;