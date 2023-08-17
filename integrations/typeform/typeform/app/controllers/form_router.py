from typing import Any, Dict, Optional

from common.models.user import Credential

from fastapi import APIRouter, Depends

from typeform.app.services import form_service
from typeform.app.services.user_service import get_user_credential

router = APIRouter(prefix="/typeform/forms")


# TODO : Migrate to dependency injection instead of Depends

# TODO : Implement interface from common plugin routes after refactoring it
@router.get("")
async def _get_forms(credential: Credential = Depends(get_user_credential)):
    return await form_service.get_forms(credential)


@router.get("/{form_id}")
async def _get_single_form(
    form_id: str, credential: Credential = Depends(get_user_credential)
):
    return await form_service.get_single_form(form_id, credential)


@router.post("/convert/standard_form")
async def _convert_form(
    form_import: Dict[str, Any],
    convert_responses: Optional[bool] = True,
    credential: Credential = Depends(get_user_credential),
):
    return await form_service.convert_form(form_import, convert_responses, credential)
