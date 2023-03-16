from classy_fastapi import Routable
from fastapi.routing import APIRoute


class CustomAPIRoute(APIRoute):

    def __init__(self, *args, **kwargs):
        if "response_model_exclude_none" in kwargs.keys():
            kwargs.pop("response_model_exclude_none")
        super().__init__(*args, response_model_exclude_none=True, **kwargs)


class CustomRoutable(Routable):

    def __init__(self, *args, **kwargs) -> None:
        if kwargs.get("route_class"):
            kwargs.pop("route_class")
        super().__init__(*args, route_class=CustomAPIRoute, **kwargs)
