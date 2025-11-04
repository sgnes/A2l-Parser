#encoding="utf-8"
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PyA2lParser", # Replace with your own username
    version="0.0.1",
    author="Sgnes",
    author_email="sgnes0514@gmai.com",
    description="Parse ASAP2 A2L file",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sgnes/A2l-Parser",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
          
      ],
    packages=[
        'a2lparser'
        ],

    python_requires='>=3.8',
)