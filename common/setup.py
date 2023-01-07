import pathlib
import setuptools

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setuptools.setup(
    name="common",
    version="0.0.1",
    description="Better collected common library.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Bibishan Pandey",
    author_email="bibishan@sireto.io",
    license="SSPL",
    classifiers=[
        "License :: OSI Approved :: SSPL License",
        "Programming Language :: Python",
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3",
)
