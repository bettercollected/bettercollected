/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-22
 * Time: 13:01
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { createRef, useEffect, useRef, useState } from 'react';

export default function Advertising() {
    const ref: any = createRef();

    const [intersected, setIntersected] = useState(false);

    useEffect(() => {
        if (ref.current !== null) {
            if (typeof window !== 'undefined') {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach((entry) => {
                        const advertisingDiv = entry.target.querySelector('.advertisingdiv');

                        if (entry.isIntersecting) {
                            setIntersected(true);
                            // ref.current.classList.add('advertising')
                            // advertisingDiv?.classList.add('advertising-animation')
                        } else {
                            setIntersected(false);
                        }
                        // we're not intersecting, so remove the class
                        // ref.current.classList.remove('advertising')
                        // advertisingDiv?.classList.remove("advertising-animation")
                    });
                });
                observer.observe(ref.current);
            }
        }
    }, [ref]);

    return (
        <div ref={ref} className={`${intersected ? 'advertising' : ''} flex flex-col bg-[#fff4e0] p-4 rounded-md shadow-md border-[1px] border-[#ffdda3]`}>
            <h2 className={'font-semibold text-2xl'}>Limited Lifetime FREE Plan</h2>
            <p>
                For a limited period and for a limited number of early users, we plan to provide a lifetime FREE individual plan. If you’re interested in using the product and providing us with your valuable feedback so that we can make the product better,
                join us by becoming a better collector.
            </p>
        </div>
    );
}
