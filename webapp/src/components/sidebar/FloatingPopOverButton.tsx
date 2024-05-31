import { useEffect, useRef, useState } from "react";

const FloatingPopOverButton = ({ content, children, className }: { content: React.ReactNode; children: React.ReactNode; className?: string }) => {
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const popoverRef = useRef<any>(null);

    const handleClickOutside = (event: any) => {
        if (popoverRef.current && !popoverRef.current.contains(event.target)) {
            setIsPopoverOpen(false);
        }
    };

    useEffect(() => {
        if (isPopoverOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        } else {
            document.removeEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isPopoverOpen]);

    const [hovered, setHovered] = useState(false);

    return (
        <div ref={popoverRef} className="p3-new text-black-600 group fixed bottom-5 right-5">
            <button onMouseOver={() => setHovered(true)} onMouseLeave={() => setHovered(false)} onClick={() => setIsPopoverOpen(!isPopoverOpen)} className=" focus:outline-none">
                {content}
            </button>
            {!isPopoverOpen && hovered && (
                <div className="bg-black-800 absolute bottom-4 right-16 rounded-lg p-1 px-2">
                    <span className="text-xs font-medium text-white">Help</span>
                </div>
            )}
            {isPopoverOpen && <div className={`shadow-floating-button absolute bottom-16 right-0 flex w-[172px] cursor-pointer flex-col gap-1 rounded-2xl bg-white p-2 ${className}`}>{children}</div>}
        </div>
    );
};

export default FloatingPopOverButton