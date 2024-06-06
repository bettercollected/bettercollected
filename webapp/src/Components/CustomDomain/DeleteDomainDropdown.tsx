import EllipsisOption from '@Components/Common/Icons/Common/EllipsisOption';
import { useModal } from '@app/components/modal-views/context';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import DeleteIcon from '@app/views/atoms/Icons/Delete';

const DeleteDomainDropdown = () => {
    const { openModal } = useModal();

    return (
        <div>
            <DropdownMenu>
                <DropdownMenuTrigger className="outline-none">
                    <Button className="!p-1 outline-none" variant={'v2GhostButton'} icon={<EllipsisOption width={24} height={24} className="text-black-700" />}></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="!z-[1000000] bg-white">
                    <DropdownMenuItem
                        className="hover:bg-black-200 flex cursor-pointer items-center gap-2 outline-none"
                        onClick={() => {
                            openModal('DELETE_CUSTOM_DOMAIN');
                        }}
                    >
                        <DeleteIcon />
                        Delete
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    );
};

export default DeleteDomainDropdown;
