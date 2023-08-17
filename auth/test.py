from typing import List

from dependency_injector import containers, providers


class C(containers.DeclarativeContainer):
    ok: List[str] = providers.Object([])


if __name__ == "__main__":
    c = C()
    c.ok().append("ok")
    print(c)
    print(c.ok())
    c2 = C()
    c2.ok().append("ok2")
    print(c2.__init__())
    print(c2.ok())
