from setuptools import setup, find_packages

setup(
    name="py-leaky-bucket",
    version="0.1.0",
    description="Leaky bucket implementation in Python with different persistence options",
    author="DuneRaccoon",
    author_email="benjamincsherro@hotmail.com",
    license="MIT",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords=["rate-limiter", "asyncio", "leaky-bucket", "redis", "sqlite3"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
    packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
    install_requires=[
        "redis>=3.5.3",
        "pytest>=6.2.4",
    ],
    python_requires=">=3.10",
)