class A:
    @staticmethod
    def ok():
        print("A")


class B(A):
    @staticmethod
    def ok():
        print("B")


if __name__ == "__main__":
    a: A = B()
    a.ok()
